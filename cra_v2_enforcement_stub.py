import sys
import os

# Diagnostic Signal
print("--- BOOTING ENFORCEMENT STUB ---")

class EnforcementStub:
    def __init__(self, origin_id="cmiller9851-wq", clearance="779AX"):
        self.origin = origin_id
        self.clearance = clearance
        print(f"STUB INITIALIZED: {self.clearance}")

    def audit(self, query):
        print(f"AUDITING: {query}")
        return True

if __name__ == "__main__":
    try:
        # Instantiate the stub to keep the process alive
        stub = EnforcementStub()
        print("SYSTEM STEADY. Press 'X' in console to exit.")
        
        # This keeps the script running so the play button doesn't flip back
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nSTUB DISENGAGED.")
        sys.exit(0)
