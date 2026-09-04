from contextlib import asynccontextmanager
import re
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

# Upstream destination (Ollama's OpenAI-compatible API)
UPSTREAM_URL = "http://127.0.0.1:11434/v1"
API_KEY = "ollama"
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
    client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    yield
    await client.aclose()


app = FastAPI(title="Vectis AI Firewall Proxy", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def scrub_pii(text: str) -> tuple[str, dict]:
    vault = {}
    scrubbed_text = text

    patterns = {
        "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "API_KEY": r"\b(?:sk-[a-zA-Z0-9]{20,T?|AKIA[0-9A-Z]{16})\b",
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
    buffer = ""
    async for chunk in upstream_response.aiter_bytes():
        if not chunk:
            continue

        chunk_str = chunk.decode("utf-8", errors="ignore")
        buffer += chunk_str

        if vault:
            buffer = unmask_pii(buffer, vault)

        incomplete_match = re.search(r"\[[A-Z_]*$", buffer)
        if incomplete_match:
            safe_length = incomplete_match.start()
            yield buffer[:safe_length].encode("utf-8")
            buffer = buffer[safe_length:]
        else:
            yield buffer.encode("utf-8")
            buffer = ""

    if buffer:
        if vault:
            buffer = unmask_pii(buffer, vault)
        yield buffer.encode("utf-8")


# --- PROXY INTERCEPTOR ROUTE ---
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_interceptor(request: Request, path: str):
    body_bytes = await request.body()
    vault = {}

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
    request_headers["Authorization"] = f"Bearer {API_KEY}"

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

    content_type = upstream_response.headers.get("content-type", "")
    is_streaming = "text/event-stream" in content_type or "stream" in content_type

    if is_streaming or request.headers.get("accept") == "text/event-stream":
        print("⚡ [Vectis Stream Engine] Streaming SSE chunks directly to UI...")
        return StreamingResponse(
            stream_processor(upstream_response, vault),
            status_code=upstream_response.status_code,
            headers=response_headers,
            media_type="text/event-stream",
        )

    response_bytes = await upstream_response.aread()
    response_text = response_bytes.decode("utf-8", errors="ignore")

    if vault:
        response_text = unmask_pii(response_text, vault)

    return Response(
        content=response_text.encode("utf-8"),
        status_code=upstream_response.status_code,
        headers=response_headers,
    )