Quickstart (add to top of README.md)

1. Clone and enter directory
   - git clone git@github.com:cmiller9851-wq/CRAprotocol.git
   - cd CRAprotocol
2. Setup
   - ./dev-setup.sh
3. Run tests
   - source .venv/bin/activate
   - make test || python -m pytest
4. Contribute
   - Create a branch module/<name>, implement small changes, add tests, open PR.

Notes:
- The project uses deterministic state transitions. Avoid adding system-level randomness in core modules.
- If you run on iOS/Pythonista, see docs/pythonista-notes.md.
