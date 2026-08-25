from contextlib import asynccontextmanager
import re
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse

# Upstream destination (Local Ollama running in OpenAI mode)
UPSTREAM_URL = "http://localhost:11434/v1"

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


# --- WEB UI FRONTEND ROUTE ---
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vectis AI Firewall Dashboard</title>
        <style>
            * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { background-color: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }
            .container { max-width: 900px; margin: 0 auto; }
            .header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #334155; padding-bottom: 1rem; margin-bottom: 2rem; }
            .badge { background: #0284c7; color: #fff; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; }
            .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
            label { font-weight: 600; display: block; margin-bottom: 0.5rem; color: #94a3b8; }
            textarea, input { width: 100%; background: #0f172a; border: 1px solid #475569; color: #fff; padding: 0.75rem; border-radius: 8px; font-size: 1rem; margin-bottom: 1rem; }
            button { background: #2563eb; color: #fff; border: none; padding: 0.75rem 1.5rem; font-size: 1rem; font-weight: 600; border-radius: 8px; cursor: pointer; width: 100%; transition: background 0.2s; }
            button:hover { background: #1d4ed8; }
            .response-box { background: #090d16; border: 1px solid #334155; border-radius: 8px; padding: 1rem; min-height: 150px; white-space: pre-wrap; font-family: monospace; line-height: 1.5; color: #38bdf8; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>🛡️ Vectis AI Firewall</h2>
                <span class="badge">Local Engine Active</span>
            </div>

            <div class="card">
                <label for="model">LLM Model Name:</label>
                <input type="text" id="model" value="llama3.2">

                <label for="prompt">Your Prompt (Include sensitive emails/phones to test PII masking):</label>
                <textarea id="prompt" rows="4">Write a brief email to john.doe@company.com and call 555-123-4567 confirming their order.</textarea>

                <button id="sendBtn" onclick="sendPrompt()">Send Through Vectis Proxy</button>
            </div>

            <div class="card">
                <label>Unmasked Response Stream (Real-Time Output):</label>
                <div id="output" class="response-box">Waiting for prompt...</div>
            </div>
        </div>

        <script>
            async function sendPrompt() {
                const prompt = document.getElementById('prompt').value;
                const model = document.getElementById('model').value;
                const outputEl = document.getElementById('output');
                const btn = document.getElementById('sendBtn');

                outputEl.textContent = '🛡️ Vectis intercepting prompt...\n';
                btn.disabled = true;

                try {
                    const response = await fetch('/chat/completions', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'text/event-stream'
                        },
                        body: JSON.stringify({
                            model: model,
                            messages: [{ role: 'user', content: prompt }],
                            stream: true
                        })
                    });

                    const reader = response.body.getReader();
                    const decoder = new TextDecoder('utf-8');
                    let buffer = '';

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\\n');
                        buffer = lines.pop();

                        for (const line of lines) {
                            const trimmed = line.trim();
                            if (!trimmed || trimmed === 'data: [DONE]') continue;

                            if (trimmed.startsWith('data: ')) {
                                try {
                                    const json = JSON.parse(trimmed.slice(6));
                                    const content = json.choices?.[0]?.delta?.content || '';
                                    outputEl.textContent += content;
                                } catch (e) {
                                    outputEl.textContent += trimmed;
                                }
                            } else {
                                outputEl.textContent += trimmed + '\\n';
                            }
                        }
                    }
                } catch (err) {
                    outputEl.textContent += '\\n❌ Error: ' + err.message;
                } finally {
                    btn.disabled = false;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


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