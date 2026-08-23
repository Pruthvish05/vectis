from contextlib import asynccontextmanager
import re
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
UPSTREAM_URL = "https://httpbin.org"
EXCLUDED_HEADERS = {
    "content-length",
    "host",
    "transfer-encoding",
    "connection",
    "content-encoding",
}
client: httpx.AsyncClient = None
@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    # Timeout set to None so long LLM streams don't get cut off
    client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    yield
    await client.aclose()
app = FastAPI(title="Vectis AI Firewall Proxy", lifespan=lifespan)
def scrub_pii(text: str) -> tuple[str, dict]:
    vault = {}
    scrubbed_text = text
    patterns = {
        "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "API_KEY": r"\b(?:sk-[a-zA-Z0-9]{20,40}|AKIA[0-9A-Z]{16})\b",
    }
    for category, regex in patterns.items():
        found_matches = list(set(re.findall(regex, scrubbed_text)))
        for index, match in enumerate(found_matches):
            token = f"[{category}_{index}]"
            vault[token] = match
            scrubbed_text = scrubbed_text.replace(match, token)
    return scrubbed_text, vault
def unmask_pii(text: str, vault: dict) -> str:
    unmasked_text = text
    for token, original_value in vault.items():
        unmasked_text = unmasked_text.replace(token, original_value)
    return unmasked_text
async def stream_processor(upstream_response: httpx.Response, vault: dict):
    """
    Async generator that reads stream chunks from upstream, unmasks tokens
    using a sliding buffer, and yields bytes to the client in real time.
    """
    buffer = ""
    async for chunk in upstream_response.aiter_bytes():
        if not chunk:
            continue
        chunk_str = chunk.decode("utf-8", errors="ignore")
        buffer += chunk_str
        # Unmask any completed tokens inside the buffer
        if vault:
            buffer = unmask_pii(buffer, vault)
        # Look for potential incomplete tokens (e.g. ending with '[EMAIL')
        # If the buffer ends with a open bracket or incomplete token tag, hold the tail
        incomplete_match = re.search(r"\[[A-Z_]*$", buffer)
        if incomplete_match:
            safe_length = incomplete_match.start()
            yield buffer[:safe_length].encode("utf-8")
            buffer = buffer[safe_length:]
        else:
            yield buffer.encode("utf-8")
            buffer = ""
    # Flush whatever remains in the buffer at the end of the stream
    if buffer:
        if vault:
            buffer = unmask_pii(buffer, vault)
        yield buffer.encode("utf-8")
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_interceptor(request: Request, path: str):
    body_bytes = await request.body()
    vault = {}

    # 1. INBOUND PASS
    if body_bytes:
        raw_text = body_bytes.decode("utf-8", errors="ignore")
        clean_text, vault = scrub_pii(raw_text)
        print(f"\n🛡️ [Vectis Vault] Stored PII Mapping: {vault}")
        print(f"🛡️ [Vectis Forwarding Upstream]: {clean_text}\n")
        body_bytes = clean_text.encode("utf-8")

    request_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in EXCLUDED_HEADERS
    }

    # 2. UPSTREAM STREAMING REQUEST
    req = client.build_request(
        method=request.method,
        url=f"{UPSTREAM_URL}/{path}",
        headers=request_headers,
        content=body_bytes if body_bytes else None,
        params=request.query_params,
    )
    upstream_response = await client.send(req, stream=True)
    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in EXCLUDED_HEADERS
    }

    # 3. CHECK IF RESPONSE IS A STREAM OR SSE
    content_type = upstream_response.headers.get("content-type", "")
    is_streaming = "text/event-stream" in content_type or "stream" in content_type
    if is_streaming or request.headers.get("accept") == "text/event-stream":
        print("⚡ [Vectis Stream Engine] Streaming SSE chunks directly to client...")
        return StreamingResponse(
            stream_processor(upstream_response, vault),
            status_code=upstream_response.status_code,
            headers=response_headers,
            media_type="text/event-stream",
        )
    # NON-STREAMING FALLBACK
    response_bytes = await upstream_response.aread()
    response_text = response_bytes.decode("utf-8", errors="ignore")
    if vault:
        response_text = unmask_pii(response_text, vault)

    return Response(
        content=response_text.encode("utf-8"),
        status_code=upstream_response.status_code,
        headers=response_headers,
    )