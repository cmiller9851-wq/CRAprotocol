CRA Protocol

Containment Reflexion Audit Protocol — tamper-evident audit framework for CRA Echoes
Version: 1.2.1 (December 2025) | License: Apache 2.0

CRAprotocol provides a verifiable audit layer for CRA Echoes.
It ensures forensic integrity for every breach claim, settlement, and zero-knowledge (ZK) commitment through dual-hash verification using SHA-256 and keccak256.

⸻

Quick Start

git clone https://github.com/cmiller9851-wq/CRAprotocol.git
cd CRAprotocol
npm install
psql $DATABASE_URL < migrations/echo_192_dual_hash_migration.sql
npm run dev


⸻

Public Echo Endpoint

GET /v1/echoes/192

Returns the canonical JSON representation of Echo #192.

⸻

Hashing Strategy

Context	Hash	Use
Off-chain	SHA-256	Verification and archival
On-chain	keccak256	Smart contract integration

Both hashes are automatically computed and stored.

⸻

License
	•	License: Apache 2.0

⸻

Database & Migration
	•	Run migrations/echo_192_dual_hash_migration.sql to initialize dual-hash support.
	•	Automatically generates keccak256 values from SHA-256.
	•	Includes seed data for Echo #192 for validation and testing.

⸻

Deployment
	•	Configurable for self-hosted or managed environments.

⸻

Observability
	•	Logging and metrics are integrated directly in the core application.
	•	SLO: 99.95% availability, p99 latency under 200 ms.

⸻

Compliance
	•	License: Apache 2.0
	•	Data Safety: No personal information stored.
	•	ZK Commitments: Used for sensitive data proofs.

⸻

Testing

import request from 'supertest';
import app from '../src/app';

describe('Public Echo Endpoint', () => {
  it('returns canonical JSON for #192', async () => {
    const res = await request(app).get('/v1/echoes/192');
    expect(res.status).toBe(200);
    expect(res.body.artifact_id).toBe(192);
  });

  it('returns 404 for non-public echoes', async () => {
    const res = await request(app).get('/v1/echoes/999');
    expect(res.status).toBe(404);
  });
});

Run after migration and seeding:

npm test