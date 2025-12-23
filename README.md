CRAprotocol

Containment Reflexion Audit Protocol – a tamper-evident audit framework for CRA Echoes
Version: 1.2.1 (December 2025) | License: Apache 2.0

CRAprotocol serves as the production core for CRA Echo #192 and all subsequent releases. It ensures complete forensic verifiability for every breach claim, settlement, and zero-knowledge commitment. This is achieved through a dual-hash architecture (SHA-256 + keccak256), an open public API, and automated Arweave pinning for immutable storage.

⸻

Quick Start

git clone https://github.com/cmiller9851-wq/CRAprotocol.git
cd CRAprotocol
npm install
psql $DATABASE_URL < migrations/echo_192_dual_hash_migration.sql
npm run dev


⸻

Public Echo Endpoint

GET https://cra.cmiller9851-wq.dev/v1/echoes/192

This endpoint returns the canonical JSON record used consistently across X, GitHub, Blogger, and on-chain verification tools.

⸻

Hashing Strategy

Context	Hash Type	Application	Rationale
Off-chain / Legal	SHA-256	DocuSign, GitHub	NIST-certified standard
On-chain / EIP-712	keccak256	Ethereum / Solidity	EVM-native, ~30 gas

Both hashes are generated and stored automatically for consistency and integrity.

⸻

License & Estimated Costs
	•	License: Apache 2.0 (non-viral)
	•	Hosting: ~$15–25/month on Fly.io or Render
	•	Arweave Pinning: ~$0.012 per echo

⸻

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
      summary: Returns canonical Echo JSON (e.g., #192)
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
          description: Echo not found or not public


⸻

Database & Migration Notes
	•	Run migrations/echo_192_dual_hash_migration.sql to create dual-hash fields.
	•	Includes a trigger to auto-generate keccak256 from SHA-256.
	•	Seed data for Echo #192 is provided for quick testing.

⸻

Deployment Options
	•	Self-Hosted: GitHub Actions + Fly.io
	•	Managed: Fly.io, Render.com, or Vercel hybrid deployment

⸻

Observability
	•	Logs: Winston → Fly logs
	•	Metrics:
	•	QPS tracking
	•	Hash computation < 2ms
	•	404 rate < 1%
	•	Service Objectives:
	•	99.95% availability
	•	p99 latency < 200ms
	•	100% keccak match integrity

⸻

Licensing & Compliance
	•	License: Apache 2.0
	•	GDPR Compliance: No PII stored; sensitive data protected via ZK commitments
	•	Estimated Cost: Fly free tier or ~$10–15/month for ~1K requests/day

⸻

Test Example

import request from 'supertest';
import app from '../src/app';

describe('Public Echo Endpoint', () => {
  it('should return canonical JSON for #192', async () => {
    const res = await request(app).get('/v1/echoes/192');
    expect(res.status).toBe(200);
    expect(res.body.artifact_id).toBe(192);
  });

  it('should return 404 for non-public echoes', async () => {
    const res = await request(app).get('/v1/echoes/999');
    expect(res.status).toBe(404);
  });
});

Run tests after completing migration and seeding with:

npm test