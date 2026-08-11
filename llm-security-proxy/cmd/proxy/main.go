package main

import (
	"log"
	"net/http"
	"os"

	"llm-security-proxy/internal/proxy"
)

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("[INFO] Proxy started on :%s", port)

	mux := http.NewServeMux()
	mux.Handle("/", proxy.NewHandler())

	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("listen and serve: %v", err)
	}
}
