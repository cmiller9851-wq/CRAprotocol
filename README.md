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

Public Echo Endpoint

After an artifact reaches PUBLIC_ECHO_READY status, it is instantly queryable:

GET https://cra.cmiller9851-wq.dev/v1/echoes/192

Returns the exact canonical JSON used across X, GitHub, Blogger, and on-chain verifiers.

Hashing Strategy

Context	Use	Reason
Off-chain / legal	SHA-256	NIST standard, DocuSign/GitHub native
On-chain / EIP-712	keccak256	Native in Solidity, ~30 gas per hash

Both hashes are stored automatically in the database.

Schema Changes & Migrations
	•	Dual-hash columns (sha256, keccak256) added to artifacts
	•	onchain_tx + zk_commitment columns for cryptographic verification
	•	echo_status ENUM for tracking artifact lifecycle (DRAFT, PUBLIC_ECHO_READY, SETTLED, DISPUTED)
	•	Auto-trigger fills keccak256 from SHA-256 on insert/update
	•	Fast indexes on keccak256 and echo_status for quick queries

License & Cost
	•	Apache 2.0 – no viral clause
	•	Running cost: ~$15–25/mo on Fly.io / Render
	•	Arweave pinning cost: ~$0.012 per echo

Contributing
	1.	Clone the repo
	2.	Run migrations: psql $DATABASE_URL < migrations/echo_192_dual_hash_migration.sql
	3.	Add new Echo artifacts following dual-hash conventions
	4.	Ensure public echoes are set to PUBLIC_ECHO_READY
	5.	Push changes and open PR for review

Contact

For questions or audits, contact the repo owner: quickpromptsolutions@yahoo.com
