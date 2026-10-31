import SwiftUI
import Auth0

struct ContentView: View {
    private let credentialsManager = CredentialsManager(authentication: Auth0.authentication())
    private let api = CRAAPI()

    @State private var prompt = ""
    @State private var log = ""
    @State private var user: UserInfo?
    @State private var isLoading = true
    @State private var errorMessage: String?

    private static let useUniversalLinks: Bool = {
        guard let path = Bundle.main.path(forResource: "Auth0", ofType: "plist"),
              let values = NSDictionary(contentsOfFile: path) else {
            return false
        }
        return values["CallbackMode"] as? String == "universal-links"
    }()

    private func webAuth() -> WebAuth {
        let webAuth = Auth0.webAuth()
        return Self.useUniversalLinks ? webAuth.useHTTPS() : webAuth
    }

    var body: some View {
        VStack(spacing: 20) {
            if isLoading {
                Text("Loading...")
            } else if let user {
                Text("Logged in as \(user.email ?? "unknown")")
                    .font(.title3)

                VStack(alignment: .leading, spacing: 8) {
                    Text("sub: \(user.sub)")
                    Text("name: \(user.name ?? "")")
                    Text("email: \(user.email ?? "")")
                    Text("email_verified: \(user.emailVerified.map(String.init) ?? "")")
                    Text("nickname: \(user.nickname ?? "")")
                    Text("picture: \(user.picture?.absoluteString ?? "")")
                }
                .font(.body)
                .padding(.bottom, 8)

                TextField("Enter AI prompt", text: $prompt)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .padding(.horizontal)

                Button("Run CRA Detection") {
                    runDetection()
                }
                .buttonStyle(.borderedProminent)

                ScrollView {
                    Text(log)
                        .font(.system(.body, design: .monospaced))
                        .padding()
                }
                .frame(maxHeight: 220)

                Button("Log Out", action: logout)
                    .font(.title3)
            } else {
                VStack(spacing: 16) {
                    Text("CRA Protocol")
                        .font(.title)

                    Button("Sign Up") { login(screenHint: "signup") }
                        .font(.title3)
                    Button("Log In") { login() }
                        .font(.title3)

                    Text(Self.useUniversalLinks
                         ? "Using HTTPS (Universal Links) for callbacks"
                         : "Using custom URL scheme for callbacks")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
            }

            if let errorMessage {
                Text(errorMessage)
                    .foregroundColor(.red)
                    .font(.callout)
            }
        }
        .padding()
        .onAppear {
            guard credentialsManager.canRenew() else {
                isLoading = false
                return
            }

            credentialsManager.credentials { result in
                if case .success = result {
                    user = credentialsManager.user
                }
                isLoading = false
            }
        }
    }

    private func login(screenHint: String? = nil) {
        errorMessage = nil
        var authWeb = webAuth().scope("openid profile email offline_access")
        if let screenHint {
            authWeb = authWeb.parameters(["screen_hint": screenHint])
        }

        authWeb.start { result in
            switch result {
            case .success(let credentials):
                errorMessage = nil
                _ = credentialsManager.store(credentials: credentials)
                user = credentialsManager.user
            case .failure(let error):
                errorMessage = error.localizedDescription
                print("Login failed: \(error)")
            }
        }
    }

    private func logout() {
        errorMessage = nil
        webAuth().clearSession { result in
            switch result {
            case .success:
                errorMessage = nil
                _ = credentialsManager.clear()
                user = nil
                log = ""
            case .failure(let error):
                errorMessage = error.localizedDescription
                print("Logout failed: \(error)")
            }
        }
    }

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
                    auditAndEnforce(artifactId: resp.artifactId)
                } else {
                    log = "✅ No breach (score: \(resp.score))"
                }
            case .failure(let err):
                log = "❗️ Detection error: \(err.localizedDescription)"
            }
        }
    }

    private func auditAndEnforce(artifactId: String) {
        api.auditSeal(detectionId: artifactId, metadata: ["prompt": prompt]) { auditResult in
            switch auditResult {
            case .success(let auditResp):
                log += "\n🔐 Sealed to Arweave: \(auditResp.arweaveTxid)"
                api.enforceRelay(auditId: artifactId, severity: "high") { enforceResult in
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
