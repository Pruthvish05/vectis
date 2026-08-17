from contextlib import asynccontextmanager
import re
import httpx
from fastapi import FastAPI, Request, Response
# Upstream destination
UPSTREAM_URL = "https://httpbin.org"
# Headers that HTTP client/server frameworks should calculate automatically
EXCLUDED_HEADERS = {
    "content-length",
    "host",
    "transfer-encoding",
    "connection",
    "content-encoding",
}
# Share a single client across requests instead of opening a new pool per request
client: httpx.AsyncClient = None
@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = httpx.AsyncClient()
    yield
    await client.aclose()
app = FastAPI(title="Vectis AI Firewall Proxy", lifespan=lifespan)
def scrub_pii(text: str) -> tuple[str, dict]:
    """Scans incoming prompt text for PII patterns, replaces them with tokens,
    and returns both the scrubbed text and the vault mapping.
    """
    vault = {}
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    found_emails = list(set(re.findall(email_pattern, text)))
    scrubbed_text = text
    for index, email in enumerate(found_emails):
        token = f"[EMAIL_{index}]"
        vault[token] = email
        scrubbed_text = scrubbed_text.replace(email, token)
    return scrubbed_text, vault
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_interceptor(request: Request, path: str):
    body_bytes = await request.body()
    if body_bytes:
        # 1. Decode bytes to string
        raw_text = body_bytes.decode("utf-8", errors="ignore")
        # 2. Scrub PII
        clean_text, vault = scrub_pii(raw_text)
        # 3. Print logs to terminal
        print(f"\n [Vectis Vault] Stored PII Mapping: {vault}")
        print(f"[Vectis Forwarding]: {clean_text}\n")
        # 4. Re-encode scrubbed text back to bytes
        body_bytes = clean_text.encode("utf-8")
    # 5. Filter out transport and length headers from incoming request
    request_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in EXCLUDED_HEADERS
    }
    # 6. Forward request upstream
    upstream_response = await client.request(
        method=request.method,
        url=f"{UPSTREAM_URL}/{path}",
        headers=request_headers,
        content=body_bytes if body_bytes else None,
        params=request.query_params,
    )
    # 7. Filter response headers before returning to client
    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in EXCLUDED_HEADERS
    }
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )