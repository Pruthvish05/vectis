# llm-security-proxy

This prototype is a local Go reverse proxy for OpenAI-compatible chat completions requests. It inspects the incoming JSON body, extracts the user prompt, prints it to the terminal, restores the original body, and forwards the request to an upstream LLM endpoint.

## What it does

- Runs locally on localhost:8080
- Accepts POST requests at /v1/chat/completions
- Reads the request JSON body without modifying it
- Logs the intercepted prompt
- Forwards the original request unchanged to an upstream endpoint
- Returns the upstream response to the client

## Architecture

- cmd/proxy/main.go: Starts the HTTP server
- internal/parser/parser.go: Parses the request JSON and extracts the prompt
- internal/proxy/proxy.go: Reads the body, logs the prompt, restores the body, and forwards the request

## Install dependencies

```bash
go mod tidy
```

## Configure the upstream endpoint

Copy the example environment file and edit it:

```bash
copy .env.example .env
```

Then set:

```bash
set UPSTREAM_URL=http://127.0.0.1:4000
```

## Start the proxy

```bash
go run ./cmd/proxy
```

## Test with curl

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Hello, my name is Ram"
      }
    ]
  }'
```

You should see the prompt logged in the terminal and the upstream server should receive the unchanged request.

## Why the body must be restored

The request body is a stream. If it is read once for inspection, the reverse proxy cannot forward it later unless the bytes are restored into a new reader. This prototype preserves the original body exactly.

## Current limitations

- No authentication
- No rate limiting
- No gRPC
- No Python security engine
- No persistence or dashboards

## Future Level 2 direction

Level 2 will evolve this into a more secure architecture where Go handles ingress and transport, while a Python-based PII/security engine evaluates the prompt and a gRPC channel passes data between the systems.
