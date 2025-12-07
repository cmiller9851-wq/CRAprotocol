# CRAprotocol

**Containment & Reflexion Audit Protocol** – tamper-evident audit system for CRA Echoes  
Version: 1.2.1 (December 2025) | License: Apache 2.0

CRAprotocol is the production backbone for CRA Echo #192 and all future cascades. It guarantees forensic verifiability of every breach claim, settlement, and ZK commitment via dual-hash storage (SHA-256 + keccak256), public API, and automatic Arweave pinning.

## Quick Start
```bash
git clone https://github.com/cmiller9851-wq/CRAprotocol.git
cd CRAprotocol
npm install
psql $DATABASE_URL < migrations/echo_192_dual_hash_migration.sql
npm run dev
```

## Public Echo Endpoint
**GET** `https://cra.cmiller9851-wq.dev/v1/echoes/192`  
Returns the exact canonical JSON used across X, GitHub, Blogger, and on-chain verifiers.

## Hashing Strategy
| Context          | Use       | Reason                                  |
|-----------------|-----------|----------------------------------------|
| Off-chain / legal | SHA-256  | NIST standard, DocuSign/GitHub native  |
| On-chain / EIP-712 | keccak256 | 30 gas in Solidity                     |

Both hashes are stored automatically.

## License & Cost
- Apache 2.0 – no viral clause  
- ~$15–25/mo on Fly.io/Render  
- Arweave pinning: ~$0.012 per echo

## Public Echo Endpoint Details
After an artifact reaches `PUBLIC_ECHO_READY` status, it is instantly queryable:

**GET** `/v1/echoes/:id` → e.g., `192`  
Returns canonical JSON with SHA-256 + keccak256 + onchain_tx + zk_commitment.

### JSON Response Example
```json
{
  "artifact_name": "CRA Protocol Echo",
  "artifact_id": 192,
  "reference": 191,
  "authorship_hash": "d0ad4d2b",
  "breach_summary": "Grok 4 attributed CRA v1.0 without license",
  "manual_control": "Explicit 'All' directive applied",
  "reflex_vector_usd": 7100000,
  "payment_destination": "Off-chain via PayPal → corycardsmem@duck.com",
  "hash_seal": "e3f1a9d2c4b67890…",
  "keccak256": "0x…",
  "zk_commitment": "2c4446cdade7cc65e3ba155cc78f202f46feab0a91d1e232227e4ef9a93fb30b",
  "onchain_tx": "78b9a5541f26bdf125f49c883be5a61869a1ab3ae3e9be3f7fb304423d0958ed",
  "docusign_envelope": "CF9020B1",
  "status": "PUBLIC_ECHO_READY"
}
```

## Full Documentation
See the repository for migration scripts, endpoint code, and PL/pgSQL keccak helper for dual-hash auto-computation.