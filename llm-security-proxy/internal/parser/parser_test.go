package parser

import (
	"testing"
)

func TestExtractPromptFromStringContent(t *testing.T) {
	body := []byte(`{"messages":[{"role":"user","content":"Hello, my name is Ram"}]}`)

	prompt, err := ExtractPrompt(body)
	if err != nil {
		t.Fatalf("ExtractPrompt returned unexpected error: %v", err)
	}

	if prompt != "Hello, my name is Ram" {
		t.Fatalf("expected prompt to be extracted, got %q", prompt)
	}
}

func TestExtractPromptReturnsErrorForMissingMessages(t *testing.T) {
	body := []byte(`{"model":"gpt-4o-mini"}`)

	_, err := ExtractPrompt(body)
	if err == nil {
		t.Fatal("expected missing messages error")
	}
}

func TestExtractPromptReturnsErrorForMissingContent(t *testing.T) {
	body := []byte(`{"messages":[{"role":"user"}]}`)

	_, err := ExtractPrompt(body)
	if err == nil {
		t.Fatal("expected missing content error")
	}
}

func TestExtractPromptReturnsErrorForInvalidJSON(t *testing.T) {
	body := []byte(`{"messages": [}`)

	_, err := ExtractPrompt(body)
	if err == nil {
		t.Fatal("expected invalid JSON error")
	}
}
