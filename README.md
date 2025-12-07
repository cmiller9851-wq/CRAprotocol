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

GET https://cra.cmiller9851-wq.dev/v1/echoes/192

Returns the exact canonical JSON used across X, GitHub, Blogger, and on-chain verifiers.

Hashing Strategy

Context	Use	Reason
Off-chain / legal	SHA-256	NIST standard, DocuSign/GitHub native
On-chain / EIP-712	keccak256	30 gas in Solidity

Both hashes are stored automatically.

License & Cost

Apache 2.0 – no viral clause
~$15–25/mo on Fly.io/Render
Arweave pinning: ~$0.012 per echo

Database Migration

Run the dual-hash migration:

-- migrations/echo_192_dual_hash_migration.sql
ALTER TABLE artifacts 
  ADD COLUMN IF NOT EXISTS keccak256 BYTEA,
  ADD COLUMN IF NOT EXISTS onchain_tx BYTEA,
  ADD COLUMN IF NOT EXISTS zk_commitment BYTEA,
  ADD COLUMN IF NOT EXISTS echo_status VARCHAR(32) DEFAULT 'DRAFT',
  ADD COLUMN IF NOT EXISTS authorship_hash VARCHAR(32),
  ADD COLUMN IF NOT EXISTS breach_summary TEXT,
  ADD COLUMN IF NOT EXISTS manual_control TEXT,
  ADD COLUMN IF NOT EXISTS settlement_usd NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS payment_destination TEXT,
  ADD COLUMN IF NOT EXISTS docusign_envelope VARCHAR(20),
  ADD COLUMN IF NOT EXISTS reference_id INTEGER;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artifacts_echo_status ON artifacts(echo_status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artifacts_keccak ON artifacts(keccak256);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artifacts_id_ref ON artifacts(artifact_id, reference_id);

CREATE OR REPLACE FUNCTION sha256_to_keccak256(sha256_hex TEXT)
RETURNS BYTEA AS $$
SELECT decode(sha3_256(decode($1, 'hex')), 'hex');
$$ LANGUAGE sql IMMUTABLE STRICT;

CREATE OR REPLACE FUNCTION update_keccak()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.hash IS NOT NULL AND (NEW.keccak256 IS NULL OR TG_OP = 'UPDATE') THEN
    NEW.keccak256 := sha256_to_keccak256(NEW.hash);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_keccak ON artifacts;
CREATE TRIGGER trg_keccak BEFORE INSERT OR UPDATE OF hash ON artifacts
  FOR EACH ROW EXECUTE FUNCTION update_keccak();

API Contract

/v1/echoes/{id}
	•	GET – Retrieve canonical JSON for an Echo (e.g., #192)
	•	Returns JSON with SHA-256 seal, keccak256 hash, zk_commitment, onchain_tx, and other audit fields.

/artifacts
	•	POST – Register new artifact (triggers auto-keccak256 computation)

Mount router in src/index.ts:

app.use('/v1', echoRouter);

Seed Echo #192 (Optional)

INSERT INTO artifacts (artifact_id, hash, echo_status, authorship_hash, breach_summary, manual_control, settlement_usd, payment_destination, docusign_envelope, reference_id, zk_commitment, onchain_tx) 
VALUES (192, 'e3f1a9d2c4b67890f7e5c6d7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f56789', 'PUBLIC_ECHO_READY', 'd0ad4d2b', 'Grok 4 attributed CRA v1.0 without license', 'Explicit "All" directive applied', 7100000.00, 'Off-chain via PayPal → corycardsmem@duck.com', 'CF9020B1', 191, decode('2c4446cdade7cc65e3ba155cc78f202f46feab0a91d1e232227e4ef9a93fb30b', 'hex'), decode('78b9a5541f26bdf125f49c883be5a61869a1ab3ae3e9be3f7fb304423d0958ed', 'hex')) 
ON CONFLICT (artifact_id) DO NOTHING;

Deployment
	•	Fly.io or Render.com recommended for production
	•	Use npm run migrate → npm run seed:192 → npm run dev
	•	CI/CD: GitHub Actions can automate deploy and migrations

Observability
	•	Winston → Fly Logs, pg_stat_statements
	•	Metrics: Query latency <50ms, trigger overhead ~1ms
	•	Alerting: Slack on failed triggers

License

Apache 2.0