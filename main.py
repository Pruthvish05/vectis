import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response

app = FastAPI(title="Vectis AI Firewall Proxy")
UPSTREAM_URL = "https://httpbin.org"


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    body_bytes = await request.body()
    if body_bytes:
            print(print(f"\n [Vectis Intercept] Raw Payload:\n{body_bytes.decode('utf-8', errors='ignore')}"))
            pass
    headers = dict(request.headers)
    headers.pop("host", None)
    async with httpx.AsyncClient() as client:
        upstream_response = await client.request(
            method=request.method,
            url=f"{UPSTREAM_URL}/{path}",
            headers=headers,
            content=body_bytes,
            params=request.query_params
        )
        return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=dict(upstream_response.headers)
    )