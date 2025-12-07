import { Router } from 'express';
import db from '../db/connection';

const router = Router();

/**
 * GET /v1/echoes/:id
 * Returns canonical JSON for a public CRA Echo.
 */
router.get('/v1/echoes/:id', async (req, res) => {
  const artifact = await db('artifacts')
    .where({ id: req.params.id })
    .orWhere({ artifact_id: req.params.id }) // numeric support
    .first();

  if (!artifact || artifact.echo_status !== 'PUBLIC_ECHO_READY') {
    return res.status(404).json({ error: 'Echo not found or not public' });
  }

  res.json({
    artifact_name: "CRA Protocol Echo",
    artifact_id: artifact.artifact_id || artifact.id,
    reference: artifact.reference_id,
    authorship_hash: artifact.authorship_hash?.slice(0,8),
    breach_summary: artifact.breach_summary,
    manual_control: artifact.manual_control,
    reflex_vector_usd: artifact.settlement_usd,
    payment_destination: artifact.payment_destination,
    hash_seal: artifact.hash,           // SHA-256
    keccak256: artifact.keccak256 ? '0x' + artifact.keccak256.toString('hex') : null,
    zk_commitment: artifact.zk_commitment,
    onchain_tx: artifact.onchain_tx,
    docusign_envelope: artifact.docusign_envelope,
    status: artifact.echo_status
  });
});

export default router;