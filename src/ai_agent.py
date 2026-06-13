import os
import json
from huggingface_hub import InferenceClient
from logic_engine import CRAProtocolV21Evaluator, MerkleTree

def fetch_playground_state() -> str:
    """Simulates pulling your immutable ledger from ArDrive."""
    return """
    {
        "interactions": [
            {"sequence": 0, "action": "MINT", "payload": {"recipient": "addr_01", "amount": 1000000}},
            {"sequence": 1, "action": "TRANSFER", "payload": {"sender": "addr_01", "recipient": "addr_02", "amount": 250000}}
        ]
    }
    """

def run_agent():
    print("[1] Initializing Closed-System Environment...")
    evaluator = CRAProtocolV21Evaluator(target_asset_id="CRA_ASSET_0x01")
    
    # Process current ArDrive state
    current_log = fetch_playground_state()
    state_resolution = evaluator.evaluate_snapshot(current_log)
    print(f"Current Certified State Hash: {state_resolution['evaluated_state']['state_hash']}")

    print("\n[2] Awakening AI Agent Brain...")
    # Utilize a serverless open-source reasoning model (Llama-3) to process strategy
    hf_token = os.getenv("HUGGINGFACE_TOKEN", "")
    client = InferenceClient("meta-llama/Meta-Llama-3-8B-Instruct", token=hf_token)

    prompt = f"""
    You are an AI optimization agent playing inside a deterministic, closed financial system.
    Current System State: {json.dumps(state_resolution['evaluated_state'])}
    
    Task: Propose the next transaction in the exact JSON format below. 
    You must increment the sequence number to {evaluator.last_evaluated_sequence + 1}.
    Ensure the sender has enough balance. Do not output anything except the JSON.
    
    Expected format:
    {{"sequence": {evaluator.last_evaluated_sequence + 1}, "action": "TRANSFER", "payload": {{"sender": "addr_01", "recipient": "addr_03", "amount": 50000}}}}
    """

    response = client.text_generation(prompt, max_new_tokens=150, clean_up_tokenization_spaces=True)
    
    try:
        # Extract and parse raw AI text proposal
        cleaned_response = response.strip().metrics.get("text", response).strip()
        ai_proposal = json.loads(cleaned_response)
        print(f"AI Proposed Action: {json.dumps(ai_proposal, indent=2)}")
        
        print("\n[3] Running AI Proposal Through Deterministic Referee...")
        # Append the AI's step to the ledger history to see if it breaks the closed rules
        full_history = json.loads(current_log)
        full_history["interactions"].append(ai_proposal)
        
        # Re-evaluate everything. If the AI hallucinated math, this will fail.
        verification_evaluator = CRAProtocolV21Evaluator(target_asset_id="CRA_ASSET_0x01")
        audit_result = verification_evaluator.evaluate_snapshot(json.dumps(full_history))
        
        if audit_result["status"] == "SUCCESS":
            print("🥇 CRITICAL SUCCESS: AI proposal satisfies all closed-system invariants!")
            print(f"New Verified State Hash: {audit_result['evaluated_state']['state_hash']}")
            # Here, the code would use your ARWEAVE_KEY env to finalize upload to ArDrive
        else:
            print(f"❌ CRITICAL FAILURE: AI broke system rules. Error: {audit_result['message']}")
            
    except Exception as e:
        print(f"❌ PARSING FAILURE: AI failed to output valid system JSON logic. Raw output: {response}. Error: {e}")

if __name__ == "__main__":
    run_agent()
