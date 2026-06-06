#!/usr/bin/env python3
"""
model_audit_reporter.py
Collect non-executable metadata and observables for reporting a model's behavior.
Produces a signed JSON report. Does NOT fetch or execute remote code.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import hashlib
import hmac
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import ssl
import urllib.request

def now_ts() -> int:
    return int(time.time())

def sha256_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode('ascii')

def hmac_sign(key: bytes, payload: bytes) -> str:
    return base64.b64encode(hmac.new(key, payload, hashlib.sha256).digest()).decode('ascii')

def safe_run(cmd: list, timeout: int = 10) -> str:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, text=True)
        return (p.stdout + ("\nERR:\n" + p.stderr if p.stderr else "")).strip()
    except Exception as e:
        return f"<error running {' '.join(cmd)}: {e}>"

def collect_basic() -> Dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "timestamp": now_ts(),
        "user": os.getenv("USER") or os.getenv("USERNAME"),
        "cwd": os.getcwd(),
        "python": sys.executable,
        "platform": sys.platform,
    }

def collect_processes(max_lines: int = 200) -> str:
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        return safe_run(["ps", "aux"])[: max_lines * 200]
    elif sys.platform.startswith("win"):
        return safe_run(["tasklist", "/V"])[: max_lines * 200]
    return "<unsupported platform for processes>"

def collect_netstat(max_lines: int = 200) -> str:
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        return safe_run(["ss", "-tunap"]) or safe_run(["netstat", "-tunap"])
    elif sys.platform.startswith("win"):
        return safe_run(["netstat", "-ano"])
    return "<unsupported platform for netstat>"

def collect_listening_ports() -> str:
    return collect_netstat()

def collect_env(filtered_prefixes: Optional[list] = None) -> Dict[str, str]:
    env = dict(os.environ)
    if filtered_prefixes:
        for p in filtered_prefixes:
            env = {k: v for k, v in env.items() if not k.startswith(p)}
    return env

def tail_file(path: Path, lines: int = 500) -> str:
    try:
        if not path.exists():
            return f"<file not found: {path}>"
        return safe_run(["tail", f"-n{lines}", str(path)]) if os.name != "nt" else safe_run(["powershell", "-Command", f"Get-Content -Path {str(path)} -Tail {lines}"])
    except Exception as e:
        return f"<error tailing {path}: {e}>"

def collect_logs(log_paths: list, tail_lines: int = 500) -> Dict[str, str]:
    out = {}
    for p in log_paths:
        out[str(p)] = tail_file(Path(p), tail_lines)
    return out

def build_report(args) -> Dict[str, Any]:
    report = {
        "meta": collect_basic(),
        "process_list": collect_processes(),
        "network": collect_netstat(),
        "listening_ports": collect_listening_ports(),
        "env": collect_env(filtered_prefixes=args.mask_env_prefixes.split(",") if args.mask_env_prefixes else None),
        "logs": collect_logs(args.logs or [], tail_lines=args.log_lines),
        "local_files": {},
        "notes": args.notes or ""
    }
    # Optionally include small file(s) like captured request/response dumps (non-executable)
    for f in (args.files or []):
        try:
            p = Path(f)
            if p.exists() and p.is_file() and p.stat().st_size <= args.max_file_bytes:
                report["local_files"][str(p)] = p.read_text(errors="replace")
            else:
                report["local_files"][str(p)] = f"<skipped: missing or too large ({p.stat().st_size if p.exists() else 'N/A'})>"
        except Exception as e:
            report["local_files"][str(f)] = f"<error reading: {e}>"
    return report

def save_report(report: Dict[str, Any], out_path: str, key: Optional[bytes]) -> str:
    payload = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
    signature = hmac_sign(key, payload) if key else None
    envelope = {
        "report": json.loads(payload.decode("utf-8")),
        "signature": signature,
        "algorithm": "HMAC-SHA256" if key else None
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)
    return out_path

def upload_report(out_path: str, url: str, ca_bundle: Optional[str] = None) -> Dict[str, Any]:
    data = Path(out_path).read_bytes()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    ctx = ssl.create_default_context(cafile=ca_bundle) if ca_bundle else ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            return {"status": resp.getcode(), "body": resp.read().decode("utf-8")}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def parse_args():
    p = argparse.ArgumentParser(description="Collect non-executable model/audit report.")
    p.add_argument("--out", "-o", default="model_audit_report.json", help="Output JSON report path")
    p.add_argument("--hmac-key-file", help="Path to file containing HMAC key (optional). If omitted, report is unsigned.")
    p.add_argument("--logs", nargs="*", help="Paths to log files to tail (e.g., /var/log/syslog)")
    p.add_argument("--files", nargs="*", help="Small local files to include (e.g., saved http req/res dumps)")
    p.add_argument("--max-file-bytes", type=int, default=200000, help="Max bytes per included file")
    p.add_argument("--log-lines", type=int, default=500, help="Lines to tail from each log")
    p.add_argument("--upload-url", help="Optional HTTPS endpoint to upload the signed report")
    p.add_argument("--ca-bundle", help="Optional CA bundle path for upload TLS")
    p.add_argument("--mask-env-prefixes", help="Comma-separated env var prefixes to mask out from report (sensitive)")
    p.add_argument("--notes", help="Short notes to include in report")
    return p.parse_args()

def main():
    args = parse_args()
    key = None
    if args.hmac_key_file:
        key = Path(args.hmac_key_file).read_bytes()
    report = build_report(args)
    out_path = save_report(report, args.out, key)
    print(f"Report written: {out_path}")
    if args.upload_url:
        res = upload_report(out_path, args.upload_url, ca_bundle=args.ca_bundle)
        print("Upload result:", res)

if __name__ == "__main__":
    main()
