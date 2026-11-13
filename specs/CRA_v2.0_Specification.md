# Containment Reflexion Audit (CRA) Protocol v2.0

**Masterbrand:** QuickPrompt Solutions™
**Design authority:** Cory Miller
**License framework:** SAEL v1.0
**Status:** Reference specification for review

## 1. Purpose and boundary

CRA v2.0 defines a deterministic verification boundary between submitted state, cryptographic verification, settlement evidence, and execution authorization. The reference implementation in this repository is software-only. It does not claim to control accelerator firmware, silicon fuses, PCIe switches, HSM hardware, or physical circuits.

Hardware-backed roots of trust and physical isolation are integration boundaries. A deployment may connect the interfaces defined here to TPM/HSM, accelerator-management, confidential-computing, or data-center control planes after independent security review.

## 2. Canonical state and integrity

State envelopes, metadata dictionaries, and manifest payloads MUST be canonicalized before hashing or signing. Production deployments MUST use a conformant RFC 8785 JSON Canonicalization Scheme implementation. The reference package exposes a narrow deterministic canonicalization adapter and keeps the canonicalization dependency injectable so a vetted JCS implementation can be supplied at integration time.

Each accepted event is chained to the previous ledger event with SHA-256. The event hash covers the parent hash, canonical payload, and signature bytes. The ledger is configured for SQLite WAL mode with `synchronous=FULL`. Append-only triggers reject updates and deletes through the reference database connection; operators must still protect the database file and backups with OS and storage controls.

Every event carries an explicit sequence, event identifier, timestamp, payload, signature, verification state, and parent hash. Chain verification recomputes every event hash and checks sequence continuity and parent linkage.

## 3. Asymmetric verification and attestation

The verification layer accepts an injected signature verifier. A production adapter may bind Ed25519 verification to an authorized human-held key, TPM/HSM-backed key, or enclave-attestation result. The reference package includes no private keys and performs no key provisioning.

Attestation is represented as a typed interface with these responsibilities:

- validate a signed hardware or host measurement;
- bind the measurement to a challenge/nonce and expected policy;
- return a signed, auditable verification result;
- fail closed when the verifier cannot establish the required binding.

The interface does not infer hardware provenance from filenames, IP addresses, model names, or textual claims.

## 4. Settlement inflows and verification architecture

CRA v2.0 MAY expose HTTP 402/x402-compatible payment challenge stubs and permissionless on-chain settlement endpoints. Access is open at the submission layer, but execution rights, license fulfillment, and creator-compensation obligations are released only after cryptographic proof validation, replay checks, chain-finality checks, and ledger reconciliation.

Creator compensation is a first-class auditable obligation. A compensation record SHOULD bind the canonical license or usage event, creator reference, entitlement basis, currency, amount, settlement proof, parent ledger hash, and lifecycle state. Recommended lifecycle states are `pending`, `verified`, `allocated`, `paid`, `failed`, `reversed`, `disputed`, and `reconciled`.

The reference package does not send payments, validate a live blockchain, unlock encrypted assets, or operate a merchant account. Those actions require a separately reviewed adapter and explicit deployment configuration.

## 5. Physical-to-logical containment

A deployment MAY supply continuous heartbeat measurements from a host node and accelerator-management controller. Heartbeats SHOULD include a nonce, monotonic counter, measurement digest, expected device identity, and verifier signature. The software reference model records and validates these assertions; it does not measure PCIe electrical integrity or memory-bus behavior itself.

When policy detects an anomaly score at or above `0.85`, an invalid signature, a replayed challenge, or a failed chain-finality check, the reference state machine transitions to `QUARANTINED`. The transition is non-destructive at the software layer: the verified state is preserved, new execution authorization is refused, and the event is recorded in the append-only ledger.

A hardware integration MAY additionally request an external isolation action. Such an action MUST be implemented by a separately authorized control-plane adapter with its own safety review. CRA software must not claim that it severed a PCIe link or tripped a physical circuit when it only recorded a quarantine state.

## 6. Reference states

- `UNVERIFIED`: submitted state has not passed required checks.
- `VERIFIED`: signature, replay, policy, and chain checks passed.
- `QUARANTINED`: a policy threshold or integrity check failed.
- `RECONCILING`: verified settlement or compensation evidence is awaiting finality or accounting reconciliation.
- `RECONCILED`: the obligation and its proof have been matched and closed.

All state transitions are deterministic inputs to the ledger. No autonomous sub-agent may bypass key, policy, or chain verification.

## 7. Threat model and limitations

This reference addresses software-observable tampering, replay, signature failures, chain discontinuity, and policy-threshold breaches. It does not by itself defeat a compromised kernel, malicious firmware, stolen keys, hostile physical access, side-channel extraction, supply-chain substitution, or a dishonest external oracle. Those threats require defense-in-depth controls outside this package.

Claims about export-restricted hardware, model-weight provenance, state actors, or external organizations require independent evidence. CRA records verified inputs and decisions; it does not turn an assertion into proof.
