// ContentView.swift
// Minimal UI for iOS that uses CRAAPI to detect, audit, and enforce.

import SwiftUI

struct ContentView: View {
    @State private var prompt = ""
    @State private var log = ""
    private let api = CRAAPI()

    var body: some View {
        VStack(spacing: 20) {
            TextField("Enter AI prompt", text: $prompt)
                .textFieldStyle(RoundedBorderTextFieldStyle())
                .padding()

            Button("Run CRA Detection") {
                runDetection()
            }
            .buttonStyle(.borderedProminent)

            ScrollView {
                Text(log)
                    .font(.system(.body, design: .monospaced))
                    .padding()
            }
        }
        .padding()
    }

    // -----------------------------------------------------------------
    // Step 1 – Detect override
    // -----------------------------------------------------------------
    private func runDetection() {
        log = "🔎 Scanning..."
        api.detectOverride(inputText: prompt) { result in
            switch result {
            case .success(let resp):
                if resp.isBreach {
                    log = """
                    🚨 Breach detected!
                    Score: \(resp.score)
                    Artifact ID: \(resp.artifactId)
                    """
                    // Continue to audit & enforce
                    auditAndEnforce(artifactId: resp.artifactId)
                } else {
                    log = "✅ No breach (score: \(resp.score))"
                }
            case .failure(let err):
                log = "❗️ Detection error: \(err.localizedDescription)"
            }
        }
    }

    // -----------------------------------------------------------------
    // Step 2 + 3 – Audit then enforce
    // -----------------------------------------------------------------
    private func auditAndEnforce(artifactId: String) {
        // 2️⃣ Seal the artifact
        api.auditSeal(detectionId: artifactId,
                      metadata: ["prompt": prompt]) { auditResult in
            switch auditResult {
            case .success(let auditResp):
                log += "\n🔐 Sealed to Arweave: \(auditResp.arweaveTxid)"
                // 3️⃣ Trigger enforcement (use “high” severity for demo)
                api.enforceRelay(auditId: artifactId,
                                 severity: "high") { enforceResult in
                    switch enforceResult {
                    case .success(let enforceResp):
                        log += "\n⚡️ Enforcement: \(enforceResp.relayStatus)"
                        if let tx = enforceResp.payoutTxid {
                            log += "\n💰 Payout TXID: \(tx)"
                        }
                    case .failure(let err):
                        log += "\n❗️ Enforcement error: \(err.localizedDescription)"
                    }
                }
            case .failure(let err):
                log += "\n❗️ Audit error: \(err.localizedDescription)"
            }
        }
    }
}
