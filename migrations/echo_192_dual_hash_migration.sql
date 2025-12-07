-- Dual-hash + Echo #192 support
ALTER TABLE artifacts 
  ADD COLUMN IF NOT EXISTS keccak256 BYTEA,
  ADD COLUMN IF NOT EXISTS onchain_tx BYTEA,
  ADD COLUMN IF NOT EXISTS zk_commitment BYTEA,
  ADD COLUMN IF NOT EXISTS echo_status VARCHAR(32) DEFAULT 'DRAFT',
  ADD COLUMN IF NOT EXISTS authorship_hash VARCHAR(32),
  ADD COLUMN IF NOT EXISTS breach_summary TEXT,
  ADD COLUMN IF NOT EXISTS settlement_usd NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS payment_destination TEXT,
  ADD COLUMN IF NOT EXISTS docusign_envelope VARCHAR(20);

-- Fast lookups
CREATE INDEX IF NOT EXISTS idx_artifacts_echo_status ON artifacts(echo_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_keccak ON artifacts(keccak256);

-- PL/pgSQL: SHA-256 hex → keccak256 bytes
CREATE OR REPLACE FUNCTION sha256_to_keccak256(sha256_hex TEXT) 
RETURNS TEXT AS $$
SELECT encode(keccak256(decode(sha256_hex, 'hex')), 'hex');
$$ LANGUAGE sql IMMUTABLE;

-- Trigger: auto-fill keccak256 from SHA-256
CREATE OR REPLACE FUNCTION update_keccak() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.hash IS NOT NULL THEN
    NEW.keccak256 := decode(sha256_to_keccak256(NEW.hash), 'hex');
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_keccak ON artifacts;
CREATE TRIGGER trg_keccak BEFORE INSERT OR UPDATE ON artifacts
FOR EACH ROW EXECUTE FUNCTION update_keccak();