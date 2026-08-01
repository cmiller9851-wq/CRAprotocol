package main

import (
	"context"
	"encoding/binary"
	"fmt"
	"io"
	"log"
	"net"
	"sync"
	"time"
)

// Constrain memory consumption per message to protect stream buffers
const MaxMessageSizeBytes = 1024 * 1024 // 1 MB limit

type AuthoritativeNode struct {
	mu           sync.RWMutex
	sequence     uint64
	stateHash    [32]byte
	listener     net.Listener
	shutdownChan chan struct{}
}

func NewAuthoritativeNode(address string) (*AuthoritativeNode, error) {
	l, err := net.Listen("tcp", address)
	if err != nil {
		return nil, fmt.Errorf("failed to bind listener: %w", err)
	}

	return &AuthoritativeNode{
		sequence:     0,
		stateHash:    [32]byte{0x01, 0x02, 0x03}, // Initial state vector
		listener:     l,
		shutdownChan: make(chan struct{}),
	}, nil
}

// Start initiates the non-blocking accept loop
func (n *AuthoritativeNode) Start(ctx context.Context) {
	log.Printf("[+] Node listening on %s\n", n.listener.Addr().String())

	go func() {
		<-ctx.Done()
		close(n.shutdownChan)
		n.listener.Close()
	}()

	for {
		conn, err := n.listener.Accept()
		if err != nil {
			select {
			case <-n.shutdownChan:
				return // Graceful shutdown
			default:
				log.Printf("[!] Connection accept error: %v\n", err)
				continue
			}
		}

		// Handle each peer connection in an isolated goroutine
		go n.handleStream(conn)
	}
}

// handleStream processes frame-delimited binary protocol messages
func (n *AuthoritativeNode) handleStream(conn net.Conn) {
	defer conn.Close()

	// Enforce network timeouts per stream
	_ = conn.SetDeadline(time.Now().Add(5 * time.Second))

	// 1. Read 4-byte length prefix (BigEndian)
	var length uint32
	if err := binary.Read(conn, binary.BigEndian, &length); err != nil {
		return
	}

	if length > MaxMessageSizeBytes {
		log.Printf("[!] Rejected oversized payload: %d bytes\n", length)
		return
	}

	// 2. Read exact protobuf payload from wire
	buf := make([]byte, length)
	if _, err := io.ReadFull(conn, buf); err != nil {
		log.Printf("[!] Failed reading full message buffer: %v\n", err)
		return
	}

	// 3. Thread-safe state update
	n.mu.Lock()
	n.sequence++
	// Bitwise state hash mutation
	n.stateHash[n.sequence%32] ^= byte(length)
	currentSeq := n.sequence
	currentHash := n.stateHash
	n.mu.Unlock()

	// 4. Construct response frame
	respBytes := []byte(fmt.Sprintf("ACK:SEQ=%d:HASH=%x", currentSeq, currentHash[:8]))

	// 5. Write length-prefixed response back to peer
	respLen := uint32(len(respBytes))
	_ = binary.Write(conn, binary.BigEndian, respLen)
	_, _ = conn.Write(respBytes)
}

func main() {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	node, err := NewAuthoritativeNode("127.0.0.1:9090")
	if err != nil {
		log.Fatalf("Failed to initialize node: %v", err)
	}

	node.Start(ctx)
}
