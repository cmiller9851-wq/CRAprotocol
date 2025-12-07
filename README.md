# CRAprotocol

**Containment Reflexion Audit Protocol** – tamper-evident audit system for CRA Echoes  
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

GET https://cra.cmiller9851-wq.dev/v1/echoes/192

Returns the exact canonical JSON used across X, GitHub, Blogger, and on-chain verifiers.

Hashing Strategy

Context	Hash	Use	Reason
Off-chain / legal	SHA-256	DocuSign/GitHub	NIST standard
On-chain / EIP-712	keccak256	Ethereum / Solidity	30 gas, EVM-native

Both hashes are stored automatically.

License & Cost
	•	Apache 2.0 – no viral clause
	•	~$15–25/mo on Fly.io/Render
	•	Arweave pinning: ~$0.012 per echo

API Contracts (OpenAPI 3.0)

openapi: 3.0.0
info:
  title: CRA Protocol Echo Verifier API
  version: 1.2.1
servers:
  - url: https://cra-protocol.fly.dev/v1
paths:
  /echoes/{id}:
    get:
      summary: Canonical Echo JSON (e.g., #192)
      parameters:
        - name: id
          in: path
          required: true
          schema: { type: string, example: "192" }
      responses:
        '200':
          description: Public Echo
          content:
            application/json:
              schema:
                type: object
                properties:
                  artifact_name: { type: string, example: "CRA Protocol Echo" }
                  artifact_id: { type: integer, example: 192 }
                  reference: { type: integer, example: 191 }
                  authorship_hash: { type: string, example: "d0ad4d2b" }
                  breach_summary: { type: string, example: "Grok 4 attributed CRA v1.0 without license" }
                  manual_control: { type: string, example: "Explicit 'All' directive applied" }
                  reflex_vector_usd: { type: number, example: 7100000 }
                  payment_destination: { type: string, example: "Off-chain via PayPal → corycardsmem@duck.com" }
                  hash_seal: { type: string, example: "e3f1a9d2c4b67890f7e5c6d7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f56789" }
                  keccak256: { type: string, example: "0x71c835..." }
                  zk_commitment: { type: string, example: "2c4446cdade7cc65e3ba155cc78f202f46feab0a91d1e232227e4ef9a93fb30b" }
                  onchain_tx: { type: string, example: "78b9a5541f26bdf125f49c883be5a61869a1ab3ae3e9be3f7fb304423d0958ed" }
                  docusign_envelope: { type: string, example: "CF9020B1" }
                  status: { type: string, enum: ["DRAFT", "PUBLIC_ECHO_READY", "SETTLED", "DISPUTED"], example: "PUBLIC_ECHO_READY" }
        '404':
          description: Not public or missing

Database + Migration Notes
	•	Run migrations/echo_192_dual_hash_migration.sql for dual-hash fields.
	•	Triggers auto-compute keccak256 from SHA-256.
	•	Seed #192 is included for testing; queries return canonical JSON.

Deployment Options
	•	Self-Hosted: GitHub Actions + Fly.io
	•	Managed: Fly.io web deploy, Render.com, or Vercel hybrid

Observability
	•	Logs via Winston → Fly logs
	•	Metrics: QPS, hash compute (<2ms), 404 rate (<1%)
	•	SLOs: Availability 99.95%, p99 latency <200ms, 100% keccak match

Licensing & Compliance
	•	Apache 2.0
	•	GDPR-safe (no PII in echoes; ZK commitments for sensitive data)
	•	Cost: Fly free tier / $10–15/mo for 1K reqs/day

Test Example

import request from 'supertest';
import app from '../src/app';

describe('Public Echo Endpoint', () => {
  it('Should return #192 canonical JSON', async () => {
    const res = await request(app).get('/v1/echoes/192');
    expect(res.status).toBe(200);
    expect(res.body.artifact_id).toBe(192);
  });

  it('Should 404 non-public echoes', async () => {
    const res = await request(app).get('/v1/echoes/999');
    expect(res.status).toBe(404);
  });
});

Run npm test after migration and seeding.

