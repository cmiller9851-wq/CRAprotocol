import json
import os
import sys

def load_settlement_gateways(config_path="active_system_settlement_channels.json"):
    print("🔄 [id.py] Initializing dynamic endpoint extraction layer...")
    
    if not os.path.exists(config_path):
        print(f"❌ Critical Error: Configuration file '{config_path}' is missing.")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
        print("✅ [id.py] Successfully parsed active settlement channels.")
        return config_data
    except json.JSONDecodeError as e:
        print(f"❌ Operational Fault: JSON Syntax Error: {e}")
        return None

if __name__ == "__main__":
    gateways = load_settlement_gateways()
    if gateways is None:
        sys.exit(1)
    
    print(f"📋 Status: {gateways.get('system_status')}")
    print(f"🔗 Channels Mapped: {len(gateways.get('verified_channels', {}).get('email_endpoints', []))} Email / {len(gateways.get('verified_channels', {}).get('sms_endpoints', []))} SMS")
    sys.exit(0)
