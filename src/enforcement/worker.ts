// src/enforcement/worker.ts
import { Worker, Queue, Job } from 'bullmq';
import knex from '../db/connection';          // Knex instance
import fetch from 'node-fetch';               // For webhook calls
import { createReadStream } from 'fs';
import { pipeline } from 'stream/promises';
import { createHash } from 'crypto';
import { Readable } from 'stream';
import { v4 as uuidv4 } from 'uuid';

// ---------------------------------------------------------------------
// Queue configuration – must match the queue defined in router.ts
// ---------------------------------------------------------------------
const connection = {
  host: process.env.REDIS_HOST ?? 'redis',
  port: Number(process.env.REDIS_PORT ?? 6379),
};

const enforcementQueue = new Queue('enforcements', { connection });

// ---------------------------------------------------------------------
// Helper: update enforcement row
// ---------------------------------------------------------------------
async function updateEnforcement(
  id: string,
  updates: Partial<Record<string, any>>
) {
  await knex('enforcements')
    .where({ id })
    .update({ ...updates, updated_at: knex.fn.now() });
}

// ---------------------------------------------------------------------
// Action: Pin artifact to Arweave
// ---------------------------------------------------------------------
async function pinToArweave(artifactId: string, artifactHash: string) {
  // Example: stream the artifact JSON from the shared vault
  const artifactPath = `./artifacts/${artifactHash}.json`;
  const fileStream = createReadStream(artifactPath);

  // Simple mock of an Arweave upload – replace with real SDK if needed
  const arweaveEndpoint = process.env.ARWEAVE_ENDPOINT ?? 'https://arweave.net';
  const response = await fetch(`${arweaveEndpoint}/tx`, {
    method: 'POST',
    body: fileStream,
    headers: {
      'Content-Type': 'application/octet-stream',
    },
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Arweave upload failed: ${err}`);
  }

  const txId = await response.text(); // Arweave returns the transaction ID
  return txId.trim();
}

// ---------------------------------------------------------------------
// Action: Send webhook alert
// ---------------------------------------------------------------------
async function sendWebhook(url: string, payload: any) {
  const resp = await fetch(url, {
    method: 'POST',
    body: JSON.stringify(payload),
    headers: { 'Content-Type': 'application/json' },
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Webhook error ${resp.status}: ${err}`);
  }
}

// ---------------------------------------------------------------------
// Worker definition
// ---------------------------------------------------------------------
const worker = new Worker(
  'enforcements',
  async (job: Job) => {
    const { id, artifact_id, target, action } = job.data as {
      id: string;
      artifact_id: string;
      target: string;
      action: string;
    };

    // Mark job as processing
    await updateEnforcement(id, { status: 'processing' });

    try {
      // Load artifact metadata (hash, etc.)
      const artifact = await knex('artifacts')
        .where({ id: artifact_id })
        .first();

      if (!artifact) {
        throw new Error(`Artifact ${artifact_id} not found`);
      }

      let result: any = {};

      switch (action) {
        case 'pin_arweave': {
          const txId = await pinToArweave(artifact.id, artifact.hash);
          result = { txId };
          await updateEnforcement(id, {
            status: 'completed',
            tx_id: txId,
            inflow_trace: JSON.stringify({ action, txId }),
          });
          break;
        }

        case 'webhook_alert': {
          const payload = {
            artifactId: artifact.id,
            hash: artifact.hash,
            target,
            timestamp: new Date().toISOString(),
          };
          await sendWebhook(target, payload);
          result = { webhookSent: true };
          await updateEnforcement(id, {
            status: 'completed',
            inflow_trace: JSON.stringify({ action, payload }),
          });
          break;
        }

        default:
          throw new Error(`Unsupported action "${action}"`);
      }

      return result;
    } catch (err: any) {
      // Record failure, keep the job for possible retries
      await updateEnforcement(id, {
        status: 'failed',
        error_msg: err.message,
        updated_at: knex.fn.now(),
      });
      // Rethrow so BullMQ knows the job failed
      throw err;
    }
  },
  {
    connection,
    // Retry up to 3 times with exponential back‑off
    settings: {
      retryProcessDelay: 5_000,
    },
    // Optional: limit concurrency per worker instance
    concurrency: Number(process.env.WORKER_CONCURRENCY ?? 5),
  }
);

// ---------------------------------------------------------------------
// Graceful shutdown handling
// ---------------------------------------------------------------------
process.on('SIGINT', async () => {
  console.log('🛑 Worker shutting down...');
  await worker.close();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('🛑 Worker terminating...');
  await worker.close();
  process.exit(0);
});

console.log('🚀 BullMQ worker started – listening on queue "enforcements"');
