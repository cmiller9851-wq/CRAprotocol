# ao Hyper Computer Deployment

The CRAprotocol operates as a permanent process on the ao network.

### Deployment Steps (via iOS/Terminal)
1. Install `aos` via Node: `npm i -g https://get_aos.forty-two.xyz`
2. Start process: `aos CRAprotocol`
3. Load Sovereign Logic: `.load src/process/cra_core.lua`

### Integrity Lock
The **Merkle Integrity Lock** is enforced by the `Owner` variable native to the ao process, ensuring only the Origin can execute high-level audit manifests.
