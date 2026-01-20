# CRA Protocol: Merkle Integrity Lock
### QuickPrompt Solutions

This repository implements the **CRA Protocol**, a deterministic framework for cryptographic asset labeling and identity verification. It uses a Merkle Integrity Lock to create immutable roots from a set of data leaves, facilitating the **Coin Possession Cascade**.

## Technical Specifications
- **Hashing:** SHA-256 (Deterministic byte-level).
- **Dependency:** Python Standard Library only.
- **Architecture:** Modular design for "Transparency by Design" compliance.

## Usage
### Root Generation
Generate a Sovereign Signature using the CLI:
```bash
python merkle_lock.py --leaves '["LEAF_1","LEAF_2","LEAF_3"]'
