package proxy

import (
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestProxyForwardsOriginalBodyAndReturnsResponse(t *testing.T) {
	upstreamBody := ""
	upstreamServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("failed to read upstream body: %v", err)
		}
		upstreamBody = string(body)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"test"}`))
	}))
	defer upstreamServer.Close()

	oldValue := os.Getenv("UPSTREAM_URL")
	if err := os.Setenv("UPSTREAM_URL", upstreamServer.URL); err != nil {
		t.Fatalf("failed to set UPSTREAM_URL: %v", err)
	}
	defer os.Setenv("UPSTREAM_URL", oldValue)

	handler := NewHandler()
	requestBody := `{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello, my name is Ram"}]}`
	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(requestBody))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	if upstreamBody != requestBody {
		t.Fatalf("expected upstream to receive original body %q, got %q", requestBody, upstreamBody)
	}

	if !strings.Contains(w.Body.String(), `"id":"test"`) {
		t.Fatalf("expected upstream response to be returned, got %q", w.Body.String())
	}
}

func TestProxyHandlesInvalidJSON(t *testing.T) {
	upstreamServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer upstreamServer.Close()

	oldValue := os.Getenv("UPSTREAM_URL")
	if err := os.Setenv("UPSTREAM_URL", upstreamServer.URL); err != nil {
		t.Fatalf("failed to set UPSTREAM_URL: %v", err)
	}
	defer os.Setenv("UPSTREAM_URL", oldValue)

	handler := NewHandler()
	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(`{"messages": [}`))
	req.Header.Set("Content-Type", "application/json")

	w := httptest.NewRecorder()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", w.Code)
	}
}
