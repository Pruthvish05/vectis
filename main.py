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
    """
    Scans incoming prompt text against multiple PII/secret regex patterns,
    tokenizes matches by category, and returns the scrubbed text + vault.
    """
    vault = {}
    scrubbed_text = text

    # Category -> Regex Pattern mapping
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
    """Replaces tokens in the outbound response with original values from vault."""
    unmasked_text = text
    for token, original_value in vault.items():
        unmasked_text = unmasked_text.replace(token, original_value)
    return unmasked_text


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_interceptor(request: Request, path: str):
    body_bytes = await request.body()
    vault = {}

    # --- INBOUND PASS ---
    if body_bytes:
        raw_text = body_bytes.decode("utf-8", errors="ignore")
        clean_text, vault = scrub_pii(raw_text)

        print(f"\n🛡️ [Vectis Vault] Stored PII Mapping: {vault}")
        print(f"🛡️ [Vectis Forwarding Upstream]: {clean_text}\n")

        body_bytes = clean_text.encode("utf-8")

    # Filter out transport and length headers from incoming request
    request_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in EXCLUDED_HEADERS
    }

    # --- UPSTREAM CALL ---
    upstream_response = await client.request(
        method=request.method,
        url=f"{UPSTREAM_URL}/{path}",
        headers=request_headers,
        content=body_bytes if body_bytes else None,
        params=request.query_params,
    )

    # --- OUTBOUND PASS ---
    response_text = upstream_response.content.decode("utf-8", errors="ignore")

    if vault:
        response_text = unmask_pii(response_text, vault)
        print(f"🛡️ [Vectis Outbound Unmasked]: Restored {len(vault)} token(s) back to client.\n")

    response_bytes = response_text.encode("utf-8")

    # Filter response headers before returning to client
    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in EXCLUDED_HEADERS
    }

    return Response(
        content=response_bytes,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )