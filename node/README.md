# Node Protocol (Go)

This directory includes a minimal example of a production-style node implementing a length-prefixed binary protocol with concurrent stream handling.

Files
- node/proto/node_protocol.proto: Protocol Buffers definition for state vector requests/responses.
- node/cmd/node_engine/main.go: Example Go service that accepts TCP connections and handles framed messages concurrently.

Build & Run (local)

Prerequisites:
- Go 1.18+
- protoc (Protocol Buffers compiler)
- protoc-gen-go (install via `go install google.golang.org/protobuf/cmd/protoc-gen-go@latest`)

Steps:
1. Generate Go code from proto (optional for this example):

```bash
protoc --go_out=./node --go_opt=paths=source_relative node/proto/node_protocol.proto
```

2. Build:

```bash
cd node/cmd/node_engine
go build -o node_engine
```

3. Run:

```bash
./node_engine
```

Notes:
- The example intentionally keeps the protocol handler independent from generatedpb code to show framing and concurrency patterns.
- For integration, generate the protobuf Go bindings and import them in main.go.
