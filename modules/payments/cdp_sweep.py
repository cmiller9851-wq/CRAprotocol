"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

from .cdp_routing import generate_cdp_jwt

try:
    from web3 import Web3  # type: ignore
    HAS_WEB3 = True
except ImportError:
    Web3 = None
    HAS_WEB3 = False

log = logging.getLogger(__name__)

PRIMARY_WALLET = "0x421949B526e7e215a64E88E6F4cEE6ABd10a2500"
DEFAULT_SWEEP_DESTINATION = "cmillerr.cb.id"
RESOLVED_DESTINATIONS = {
    "cmillerr.cb.id": "0x421949B526e7e215a64E88E6F4cEE6ABd10a2500",
    "cmiller.cb.id": "0xeEBdcafB98ca78cD90C78260E8f84ad57176a430",
    "swervincurvin.cb.id": "0xd65691c4255963be892b21F4dBba1aE9Ac3ca068",
    "swervincurvin.base.eth": "0x421949B526e7e215a64E88E6F4cEE6ABd10a2500",
}

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
TRANSFER_SELECTOR = "0xa9059cbb"
BASE_RPC = "https://mainnet.base.org"
ETH_RPC = "https://ethereum-rpc.publicnode.com"
CB_RESOLVER = "0x1934fc75ad10d7eed51dc7a92773cac96a06be56"


class CdpSweepEngine:
    """Balances-threshold auto-sweep from the primary collection wallet
    to a designated Coinbase ID (default: cmiller.cb.id)."""

    def __init__(
        self,
        primary_wallet: str = PRIMARY_WALLET,
        sweep_destination: str = DEFAULT_SWEEP_DESTINATION,
        min_threshold_usdc: float = 5.0,
        keep_reserve_usdc: float = 0.5,
        cooldown_seconds: int = 1800,
        cdp_api_key_name: Optional[str] = None,
        cdp_private_key_pem: Optional[str] = None,
        wallet_private_key: Optional[str] = None,
        dry_run: bool = True,
        base_rpc: str = BASE_RPC,
        eth_rpc: str = ETH_RPC,
    ):
        self.primary_wallet = (Web3.to_checksum_address(primary_wallet) if Web3 else primary_wallet)
        self.sweep_destination_name = os.environ.get("SWEEP_DESTINATION", sweep_destination)
        self.min_threshold_usdc = min_threshold_usdc
        self.keep_reserve_usdc = keep_reserve_usdc
        self.cooldown_seconds = cooldown_seconds
        self.cdp_api_key_name = cdp_api_key_name or os.environ.get("CDP_API_KEY_NAME")
        self.cdp_private_key_pem = cdp_private_key_pem or os.environ.get("CDP_API_KEY_PRIVATE_KEY")
        self.wallet_private_key = wallet_private_key or os.environ.get("SWEEP_WALLET_PRIVATE_KEY")
        self.dry_run = dry_run
        self.base_rpc = base_rpc
        self.eth_rpc = eth_rpc
        self.w3_base = Web3(Web3.HTTPProvider(self.base_rpc, request_kwargs={"timeout": 30})) if Web3 else None
        self.w3_eth = Web3(Web3.HTTPProvider(self.eth_rpc, request_kwargs={"timeout": 30})) if Web3 else None
        self.sweep_ledger: List[Dict[str, Any]] = []
        self._last_sweep_ts = 0.0
        self.resolved_cache = dict(RESOLVED_DESTINATIONS)

    # ------------------------------------------------------------------ resolution
    def resolve_destination(self, name_or_addr: Optional[str] = None) -> str:
        dest = name_or_addr or self.sweep_destination_name
        if dest.startswith("0x") and len(dest) == 42:
            return Web3.to_checksum_address(dest) if Web3 else dest
        if dest in self.resolved_cache:
            return self.resolved_cache[dest]
        addr = self._resolve_cb_id(dest)
        if addr:
            self.resolved_cache[dest] = addr
            return addr
        raise ValueError(f"cannot resolve destination name: {dest}")

    def _resolve_cb_id(self, name: str) -> Optional[str]:
        """Resolves a .cb.id name via Coinbase ENS offchain CCIP-read gateway."""
        try:
            w3 = Web3()
            def nh(n):
                node = b"\x00"*32
                for label in reversed(n.split(".")):
                    node = w3.keccak(node + w3.keccak(label.encode("utf-8")))
                return "0x"+node.hex()
            def dns_encode(n):
                out = b""
                for label in n.split("."):
                    lb = label.encode("utf-8")
                    out += bytes([len(lb)]) + lb
                return out + b"\x00"
            def pad(b):
                r = len(b)%32
                return b + (b"\x00"*(32-r) if r else b"")
            dns = dns_encode(name)
            inner = bytes.fromhex("3b3b57de") + bytes.fromhex(nh(name)[2:])
            calldata = "0x9061b923" + f"{64:064x}" + f"{64+32+len(pad(dns)):064x}" + f"{len(dns):064x}" + pad(dns).hex() + f"{len(inner):064x}" + pad(inner).hex()
            d = json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to": CB_RESOLVER, "data": calldata}, "latest"]}).encode()
            req = urllib.request.Request(self.eth_rpc, d, {"Content-Type":"application/json","User-Agent":"curl/8.0"})
            res = json.load(urllib.request.urlopen(req, timeout=30))
            err = res.get("error", {})
            data = err.get("data", "") if isinstance(err, dict) else ""
            if not isinstance(data, str) or not data.startswith("0x556f1830"):
                return None
            from eth_abi import decode
            sender, urls, call_data, callback_fn, extra = decode(["address","string[]","bytes","bytes4","bytes"], bytes.fromhex(data[10:]))
            sender = Web3.to_checksum_address(sender) if Web3 else sender
            for tmpl in urls:
                url = tmpl.replace("{sender}", sender).replace("{data}", "0x"+call_data.hex())
                try:
                    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
                    gresp = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
                except Exception:
                    continue
                resp_hex = gresp.get("data", gresp.get("result",""))
                if isinstance(resp_hex,str) and resp_hex.startswith("0x"): resp_hex = resp_hex[2:]
                if not resp_hex: continue
                resp_b = bytes.fromhex(resp_hex)
                cb_call = "0x" + callback_fn.hex() + f"{64:064x}" + f"{64+32+len(pad(resp_b)):064x}" + f"{len(resp_b):064x}" + pad(resp_b).hex() + f"{len(extra):064x}" + pad(extra).hex()
                d2 = json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to": CB_RESOLVER, "data": cb_call}, "latest"]}).encode()
                req2 = urllib.request.Request(self.eth_rpc, d2, {"Content-Type":"application/json","User-Agent":"curl/8.0"})
                cb_res = json.load(urllib.request.urlopen(req2, timeout=30))
                out = cb_res.get("result","")
                if isinstance(out, str) and len(out) >= 66:
                    return Web3.to_checksum_address("0x"+out[-40:]) if Web3 else "0x"+out[-40:]
        except Exception as e:
            log.warning("cb.id resolution error: %s", e)
        return None

    # ------------------------------------------------------------------ balances
    def get_balances(self) -> Dict[str, Any]:
        """Returns live balances of the primary wallet."""
        eth_base = self._eth_balance(self.base_rpc, self.primary_wallet)
        eth_main = self._eth_balance(self.eth_rpc, self.primary_wallet)
        usdc_base = self._erc20_balance(self.base_rpc, USDC_BASE, self.primary_wallet, decimals=6)
        return {
            "primary_wallet": self.primary_wallet,
            "usdc_base": round(usdc_base, 6),
            "eth_base": round(eth_base, 6),
            "eth_mainnet": round(eth_main, 6),
            "checked_at": time.time(),
        }

    def _eth_balance(self, rpc_url: str, addr: str) -> float:
        try:
            d = json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_getBalance","params":[addr, "latest"]}).encode()
            req = urllib.request.Request(rpc_url, d, {"Content-Type":"application/json","User-Agent":"curl/8.0"})
            r = json.load(urllib.request.urlopen(req, timeout=30)).get("result")
            return int(r, 16)/1e18 if isinstance(r, str) and r.startswith("0x") else 0.0
        except Exception:
            return 0.0

    def _erc20_balance(self, rpc_url: str, token: str, holder: str, decimals: int = 6) -> float:
        try:
            calldata = "0x70a08231000000000000000000000000" + holder[2:].lower()
            d = json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to": token, "data": calldata}, "latest"]}).encode()
            req = urllib.request.Request(rpc_url, d, {"Content-Type":"application/json","User-Agent":"curl/8.0"})
            r = json.load(urllib.request.urlopen(req, timeout=30)).get("result")
            return int(r, 16)/(10**decimals) if isinstance(r, str) and r.startswith("0x") and r != "0x" else 0.0
        except Exception:
            return 0.0

    # ------------------------------------------------------------------ transfer build
    def build_transfer(self, destination: str, amount_usdc: float) -> Tuple[str, str, int]:
        """Encodes ERC-20 transfer(to, amount) calldata. Returns (to_contract, data, raw_units)."""
        units = int(amount_usdc * 1e6)
        if units <= 0:
            raise ValueError("amount must be > 0")
        dest = (Web3.to_checksum_address(destination) if Web3 else destination)[2:].lower().zfill(64)
        amt = f"{units:064x}"
        return USDC_BASE, TRANSFER_SELECTOR + dest + amt, units

    # ------------------------------------------------------------------ sweep decision
    def check(self) -> Dict[str, Any]:
        bal = self.get_balances()
        eligible = max(0.0, round(bal["usdc_base"] - self.keep_reserve_usdc, 6))
        cool = max(0, int(self.cooldown_seconds - (time.time() - self._last_sweep_ts)))
        ready = eligible >= self.min_threshold_usdc and cool == 0
        return {
            "balances": bal,
            "eligible_usdc": eligible,
            "threshold_usdc": self.min_threshold_usdc,
            "cooldown_remaining_s": cool,
            "ready_to_sweep": ready,
            "destination_name": self.sweep_destination_name,
            "resolved_destination": self.resolve_destination(),
            "mode": "dry-run" if self.dry_run else ("cdp" if (self.cdp_api_key_name and self.cdp_private_key_pem) else "raw"),
        }

    # ------------------------------------------------------------------ execute
    def sweep(self, force: bool = False, max_amount_usdc: Optional[float] = None) -> Dict[str, Any]:
        chk = self.check()
        dest = chk["resolved_destination"]
        eligible = chk["eligible_usdc"] if max_amount_usdc is None else min(chk["eligible_usdc"], max_amount_usdc)
        if not force and not chk["ready_to_sweep"]:
            return {"status": "skipped", "reason": "threshold or cooldown not met", "check": chk}
        if eligible <= 0:
            return {"status": "skipped", "reason": "no eligible balance", "check": chk}

        token_to, calldata, units = self.build_transfer(dest, eligible)

        record: Dict[str, Any] = {
            "sweep_id": f"swp_{int(time.time()):x}_{len(self.sweep_ledger)}",
            "from": self.primary_wallet,
            "to": dest,
            "to_name": self.sweep_destination_name,
            "asset": "USDC_BASE",
            "amount_usdc": eligible,
            "units": units,
            "mode": chk["mode"],
            "timestamp": time.time(),
        }

        if self.dry_run or chk["mode"] == "dry-run":
            record["status"] = "simulated"
            record["tx_hash"] = f"0xsim{int(time.time()*1000):x}"
            record["calldata_preview"] = calldata[:100]
        elif chk["mode"] == "cdp":
            record.update(self._exec_cdp(dest, eligible))
        else:
            record.update(self._exec_raw(token_to, calldata))

        if record.get("status") in ("simulated", "confirmed", "submitted"):
            self._last_sweep_ts = time.time()
        self.sweep_ledger.append(record)
        return record

    def _exec_cdp(self, destination: str, amount_usdc: float) -> Dict[str, Any]:
        """CDP REST transfer via ES256 JWT."""
        try:
            jwt = generate_cdp_jwt(self.cdp_api_key_name, self.cdp_private_key_pem,
                                   method="POST", request_uri="/v2/transactions")
            body = json.dumps({"networkId": "base-mainnet", "amount": amount_usdc,
                               "assetId": "usdc", "destination": destination}).encode()
            req = urllib.request.Request("https://api.cdp.coinbase.com/v2/transactions", body,
                                        {"Content-Type": "application/json",
                                         "Authorization": f"Bearer {jwt}", "User-Agent":"CRA-Sweep/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
            return {"status": "submitted", "rail": "cdp", "response": resp,
                    "tx_hash": resp.get("transaction",{}).get("transactionHash","")}
        except urllib.error.HTTPError as e:
            return {"status": "failed", "error": f"CDP HTTP {e.code}", "detail": e.read().decode()[:200]}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def _exec_raw(self, token_to: str, calldata: str) -> Dict[str, Any]:
        """Raw signed ERC-20 transfer via wallet private key."""
        if not self.wallet_private_key:
            return {"status": "failed", "error": "SWEEP_WALLET_PRIVATE_KEY not configured"}
        try:
            w3 = self.w3_base
            acct = w3.eth.account.from_key(self.wallet_private_key)
            if acct.address.lower() != self.primary_wallet.lower():
                return {"status": "failed", "error": f"key address {acct.address} != primary {self.primary_wallet}"}
            nonce = w3.eth.get_transaction_count(acct.address)
            tx = {
                "to": token_to,
                "data": calldata,
                "value": 0,
                "gas": 90000,
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
                "chainId": 8453,
            }
            signed = acct.sign_transaction(tx)
            txh = w3.eth.send_raw_transaction(signed.rawTransaction)
            return {"status": "submitted", "rail": "raw_tx", "tx_hash": "0x" + txh.hex()}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    # ------------------------------------------------------------------ reporting
    def status(self) -> Dict[str, Any]:
        bal = self.get_balances()
        dest = self.resolve_destination()
        same = dest.lower() == self.primary_wallet.lower()
        return {
            "primary_wallet": self.primary_wallet,
            "sweep_destination": f"{self.sweep_destination_name} -> {dest}",
            "threshold_usdc": self.min_threshold_usdc,
            "reserve_usdc": self.keep_reserve_usdc,
            "cooldown_s": self.cooldown_seconds,
            "balances": bal,
            "warning": "sweep destination equals primary wallet (no-op)" if same else None,
            "total_swept_usdc": round(sum(r["amount_usdc"] for r in self.sweep_ledger if r.get("status") in ("simulated","confirmed","submitted")), 4),
            "sweeps_count": len(self.sweep_ledger),
            "last_sweep": self.sweep_ledger[-1] if self.sweep_ledger else None,
            "mode": "dry-run" if self.dry_run else "live",
        }
