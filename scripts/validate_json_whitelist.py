#!/usr/bin/env python3
"""Validate the supported CRAprotocol JSON manifests.

This intentionally validates a small, explicit set of operational manifests.
The repository also contains historical exports that are not JSON documents;
they remain untouched and are not silently treated as production inputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# Keep this list explicit: adding a manifest to the validation contract should
# be a deliberate code review decision.
JSON_WHITELIST = (
    "config/settlement_routing.json",
    "active_system_settlement_channels.json",
    "CRA_MANIFEST.json",
    "CRA_Protocol_v_2_2.json",
    "MASTER_TRUST_MANIFEST.json",
    "Settlement_Protocol_v1.json",
    "settlement_manifest.json",
    "manifests/supreme_manifest.json",
    "schemas/CRA_Local_Node_Attestation.json",
    "schemas/CRA_Merkleized_Proof_Aggregation.json",
    "schemas/CRA_Verifier_Audit_Response.json",
    "schemas/composite-api-response.schema.json",
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for relative_path in JSON_WHITELIST:
        path = root / relative_path
        if not path.is_file():
            failures.append(f"missing: {relative_path}")
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            failures.append(f"invalid: {relative_path}: {exc}")

    if failures:
        print("JSON whitelist validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"Validated {len(JSON_WHITELIST)} whitelisted CRAprotocol JSON manifests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
