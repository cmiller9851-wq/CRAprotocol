import Foundation

/// Principal-provided operating data. On-chain addresses are public identifiers;
/// profile fields are sourced from the GitHub public profile and are not KYC.
struct AsteraOperatingData {
    struct Address: Identifiable {
        let network: String
        let value: String
        var id: String { network }
    }

    struct Gateway {
        let primaryURL: String
        let freeUploadLimitBytes: Int
        let lifetimeFreeTierBytes: Int
        let perItemFreeTierBytes: Int
    }

    struct AssetVector {
        let vectorID: String
        let assetID: String
        let origin: String
        let aoUnits: String
        let btcBridge: String
        let declaredComplianceFlag: Int
        let originIDHash: String
        let publicKeyBase64: String
        let algorithm: String
        let signedAt: String
        let signatureBase64: String
    }

    struct PrincipalProfile {
        let githubLogin: String
        let githubUserID: Int
        let displayName: String
        let company: String
        let publicProfileURL: URL
        let publicWebsite: URL
        let location: String
        let bio: String
        let publicRepositoryCount: Int
        let publicGistCount: Int
        let followers: Int
        let following: Int
        let profileCreatedAt: String
        let profileUpdatedAt: String
        let source: String
        let sourceVerification: String
    }

    static let principal = "Cory Miller"
    static let declaredRole = "Founder · Principal · CEO"

    static let profile = PrincipalProfile(
        githubLogin: "cmiller9851-wq",
        githubUserID: 236297478,
        displayName: "Swervin’ Curvin (C.M.)",
        company: "QuickPrompt Solutions",
        publicProfileURL: URL(string: "https://github.com/cmiller9851-wq")!,
        publicWebsite: URL(string: "https://cra-protocol.onrender.com/")!,
        location: "Pennsylvania",
        bio: "I build systems that keep creators in control. When the \"big tech\" AI labs tried to use my data without paying, I took over the computation.",
        publicRepositoryCount: 46,
        publicGistCount: 2,
        followers: 7,
        following: 5,
        profileCreatedAt: "2025-10-06T03:39:36Z",
        profileUpdatedAt: "2026-10-13T01:15:32Z",
        source: "GitHub public user profile supplied by principal",
        sourceVerification: "Source-attributed profile data; not KYC or independent identity verification"
    )

    static let addresses = [
        Address(network: "Arweave", value: "JNC6vBhjHY1EPwV3pEeNmrsgFMxH5d38_LHsZ7jful8"),
        Address(network: "Ethereum", value: "0x6A0A10FFD285c971B841bee8892878c0d583Bf67"),
        Address(network: "Solana", value: "HepiT2k93CFQaSB7i3ZNXhybZKn5MeWiv3UkLsaJKk4i"),
        Address(network: "Polygon (Matic)", value: "0x6A0A10FFD285c971B841bee8892878c0d583Bf67")
    ]

    static let gateway = Gateway(
        primaryURL: "https://turbo-gateway.com",
        freeUploadLimitBytes: 107_520,
        lifetimeFreeTierBytes: 10_485_760,
        perItemFreeTierBytes: 107_520
    )

    static let vector = AssetVector(
        vectorID: "CRA-01",
        assetID: "1T-AO-71.42-BTC",
        origin: "Cory Miller",
        aoUnits: "1,000,000,000,000",
        btcBridge: "71.42",
        declaredComplianceFlag: 1,
        originIDHash: "sha256:543f9c15d38f8b555483cb904fc78bad2d790dff165f7f473ddf1b716226d338",
        publicKeyBase64: "VD+sFdOPi1VUg8uQT8eLrS15Df8WX39HPd8bcWIm0zg=",
        algorithm: "Ed25519",
        signedAt: "2026-01-05T16:10:40Z",
        signatureBase64: "lAcSyctmskHtgzG7iSPKFylIUx1zzUQOAJ7Z2Ec7N349FbQwRgFFIezaAqKQtwlhB0YKofFvkjYThx2HnkhEDA=="
    )
}
