# PATRIOT PALM TREE — 10-minute architecture overview

## Goal
Provide a short, high-level description new contributors can read in ~5 minutes to get productive.

## Core concepts
- CRA Mathematical Kernel — a pure, deterministic state transformer (3D state vector: Liquid Capital, Protocol Claims, Sovereign Anchors). No network or DB required to reason about correctness.
- Patriot Protocol Hyper Beam — custom runtime integration layer used for constrained execution on mobile/edge clients. Treated as a runtime black box by most contributors.
- REDA-Corporate — administrative root and node layer; interfaces to external settlement rails (fiat anchors, Stripe).

## Primary components
- core/ — CRA kernel implementation and tests
- modules/ — small, isolated features (atomic, concurrency-safe)
- runtimes/ — runtime adapter code for specific environments (Pythonista, mobile execution runtimes)
- infra/ — CI, deployment, and tooling

## Contribution flow
1. Read this one-pager + CONTRIBUTING.md
2. Pick a good-first-module issue — small, self-contained
3. Implement following module-spec and add tests
4. PR -> auto-check (CI) -> review -> merge

## Quick diagram (conceptual)
[Developer] -> [modules/*] -> [core/kernel] -> [runtimes/*] -> [REDA (external anchor)]

## Notes for contributors
- Treat Patriot Protocol Hyper Beam as black-box runtime. Modules must be deterministic and runnable in standard Python for tests.
- The dev-setup includes Pythonista notes to run locally if contributors are using iOS/Pythonista.
