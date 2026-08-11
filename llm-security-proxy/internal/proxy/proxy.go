package proxy

import (
	"bytes"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"

	"llm-security-proxy/internal/parser"
)

const maxBodyBytes = 1 << 20 // 1 MB

// NewHandler creates a reverse proxy that inspects chat completions requests.
func NewHandler() http.Handler {
	upstreamURL := strings.TrimSpace(os.Getenv("UPSTREAM_URL"))
	if upstreamURL == "" {
		upstreamURL = "http://127.0.0.1:4000"
	}

	proxy := httputil.NewSingleHostReverseProxy(parseURL(upstreamURL))
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Printf("[ERROR] Upstream connection failure: %v", err)
		http.Error(w, "upstream connection failure", http.StatusBadGateway)
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/v1/chat/completions" {
			http.NotFound(w, r)
			return
		}

		log.Printf("[INFO] Incoming request: %s %s", r.Method, r.URL.Path)

		body, err := readBody(r)
		if err != nil {
			if err == errBodyTooLarge {
				http.Error(w, "request body too large", http.StatusRequestEntityTooLarge)
				return
			}
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		prompt, err := parser.ExtractPrompt(body)
		if err != nil {
			log.Printf("[ERROR] %v", err)
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		log.Printf("[INFO] Intercepted prompt: %s", prompt)

		log.Printf("[INFO] Forwarding request upstream")
		restoredBody := io.NopCloser(bytes.NewReader(body))
		r.Body = restoredBody
		r.ContentLength = int64(len(body))
		r.GetBody = func() (io.ReadCloser, error) {
			return io.NopCloser(bytes.NewReader(body)), nil
		}

		proxy.ServeHTTP(w, r)
	})
}

var errBodyTooLarge = fmt.Errorf("request body too large")

func readBody(r *http.Request) ([]byte, error) {
	if r.Body == nil {
		return nil, nil
	}

	body, err := io.ReadAll(io.LimitReader(r.Body, maxBodyBytes+1))
	if err != nil {
		return nil, err
	}
	if len(body) > maxBodyBytes {
		return nil, errBodyTooLarge
	}

	return body, nil
}

func parseURL(raw string) *url.URL {
	parsed, err := url.Parse(raw)
	if err != nil {
		panic(fmt.Sprintf("invalid UPSTREAM_URL: %v", err))
	}
	return parsed
}
