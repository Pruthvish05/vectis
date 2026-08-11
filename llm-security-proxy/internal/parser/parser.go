package parser

import (
	"encoding/json"
	"fmt"
)

// RequestPayload represents the minimal structure needed for a chat completions request.
type RequestPayload struct {
	Messages []struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	} `json:"messages"`
}

// ExtractPrompt reads the request body and returns the first user prompt.
func ExtractPrompt(body []byte) (string, error) {
	var payload RequestPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		return "", fmt.Errorf("invalid JSON: %w", err)
	}

	if len(payload.Messages) == 0 {
		return "", fmt.Errorf("missing messages")
	}

	for _, msg := range payload.Messages {
		if msg.Role == "user" && msg.Content != "" {
			return msg.Content, nil
		}
	}

	return "", fmt.Errorf("missing message content")
}
