/**
 * CRA Protocol – Drift Detection
 * --------------------------------
 * Computes a SHA‑256‑based drift score for incoming AI logs,
 * normalizes it to the 0‑1 range, and stores a breach artifact
 * when the score exceeds the supplied threshold.
 */

const crypto = require('crypto');
const { v4: uuid } = require('uuid');
const knex = require('../db/knex'); // configure in src/db/knex.js

/**
 * Detect drift in a batch of logs.
 *
 * @param {string[]} logs      – Array of log strings.
 * @param {number}  threshold – Score above which a breach is recorded.
 * @returns {Promise<Object>}  – { driftScore, artifactId?, status }
 */
async function detectDrift(logs, threshold = 0.5) {
  if (!Array.isArray(logs) || logs.length === 0) {
    throw new Error('logs must be a non‑empty array');
  }

  // Baseline hash (static anchor)
  const baseline = crypto
    .createHash('sha256')
    .update('CRA_LEGACY_ANCHOR')
    .digest('hex');

  // Hash the incoming logs as a single JSON string
  const logHash = crypto
    .createHash('sha256')
    .update(JSON.stringify(logs))
    .digest('hex');

  // Compute raw byte‑wise distance
  let rawDiff = 0;
  for (let i = 0; i < logHash.length; i += 2) {
    const a = parseInt(logHash.slice(i, i + 2), 16);
    const b = parseInt(baseline.slice(i, i + 2), 16);
    rawDiff += Math.abs(a - b);
  }

  // Normalise to 0‑1 (max possible diff = 256 * (hashLength/2))
  const maxDiff = 256 * (logHash.length / 2);
  const driftScore = rawDiff / maxDiff;

  // If breach, persist artifact
  if (driftScore > threshold) {
    const artifactId = uuid();
    await knex('artifacts').insert({
      id: artifactId,
      hash: logHash,
      lineage: JSON.stringify({
        source: 'logs',
        logsCount: logs.length,
        receivedAt: new Date().toISOString(),
      }),
      drift_score: driftScore,
    });
    return { driftScore, artifactId, status: 'breach' };
  }

  // Clean result
  return { driftScore, status: 'clean' };
}

module.exports = { detectDrift };
