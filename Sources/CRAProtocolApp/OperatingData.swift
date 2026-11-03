import Foundation

/// Operating data supplied by the principal. These are declarations and
/// configuration references, not independently verified balances or custody.
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

    static let principal = "Cory Miller"
    static let declaredRole = "Founder · Principal · CEO"

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
