-- ==============================================================
-- CRA Protocol: Echo #192 Dual-Hash Migration
-- SHA-256 (off-chain) + keccak256 (on-chain/EVM)
-- ==============================================================

-- 1. Add columns for dual-hash, on-chain tx, zk commitments, and echo status
ALTER TABLE artifacts 
  ADD COLUMN IF NOT EXISTS keccak256 BYTEA,
  ADD COLUMN IF NOT EXISTS onchain_tx BYTEA,
  ADD COLUMN IF NOT EXISTS zk_commitment BYTEA,
  ADD COLUMN IF NOT EXISTS echo_status VARCHAR(32) DEFAULT 'DRAFT';

-- 2. Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_artifacts_echo_status ON artifacts(echo_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_keccak ON artifacts(keccak256);

-- 3. Trigger to auto-fill keccak256 from SHA-256 on insert/update
CREATE OR REPLACE FUNCTION update_keccak()
RETURNS TRIGGER AS $$
BEGIN
  NEW.keccak256 = decode(sha256_to_keccak256(encode(NEW.hash, 'hex')), 'hex');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Remove old trigger if it exists
DROP TRIGGER IF EXISTS trg_keccak ON artifacts;

-- Create new trigger
CREATE TRIGGER trg_keccak BEFORE INSERT OR UPDATE ON artifacts
  FOR EACH ROW EXECUTE FUNCTION update_keccak();

-- ==============================================================
-- Migration complete: all new artifacts now support dual-hash
-- ==============================================================