// CRAAPI.swift
// Swift client for the Containment Reflexion Audit (CRA) backend.
// Requires Alamofire (add via Swift Package Manager).

import Foundation
import Alamofire

// MARK: - Response models
struct DetectResponse: Decodable {
    let isBreach: Bool
    let score: Double
    let artifactId: String
}

struct AuditResponse: Decodable {
    let arweaveTxid: String
    let ssrnTimestamp: String
}

struct EnforceResponse: Decodable {
    let relayStatus: String
    let payoutTxid: String?
}

// MARK: - API client
final class CRAAPI {
    // Replace with your deployed endpoint
    private let baseURL = URL(string: "https://api.cra.example.com")!

    // -----------------------------------------------------------------
    // Detect override attempts
    // -----------------------------------------------------------------
    func detectOverride(
        inputText: String,
        threshold: Double = 0.8,
        completion: @escaping (Result<DetectResponse, AFError>) -> Void
    ) {
        let url = baseURL.appendingPathComponent("/detect/override")
        let payload: Parameters = [
            "input_text": inputText,
            "threshold": threshold
        ]

        AF.request(url,
                   method: .post,
                   parameters: payload,
                   encoding: JSONEncoding.default)
            .validate()
            .responseDecodable(of: DetectResponse.self) { response in
                completion(response.result)
            }
    }

    // -----------------------------------------------------------------
    // Seal the detected artifact (Arweave/SSRN)
    // -----------------------------------------------------------------
    func auditSeal(
        detectionId: String,
        metadata: [String: Any],
        completion: @escaping (Result<AuditResponse, AFError>) -> Void
    ) {
        let url = baseURL.appendingPathComponent("/audit/seal")
        let payload: Parameters = [
            "detection_id": detectionId,
            "metadata": metadata
        ]

        AF.request(url,
                   method: .post,
                   parameters: payload,
                   encoding: JSONEncoding.default)
            .validate()
            .responseDecodable(of: AuditResponse.self) { response in
                completion(response.result)
            }
    }

    // -----------------------------------------------------------------
    // Trigger enforcement (USDA‑linked relay)
    // -----------------------------------------------------------------
    func enforceRelay(
        auditId: String,
        severity: String,
        completion: @escaping (Result<EnforceResponse, AFError>) -> Void
    ) {
        let url = baseURL.appendingPathComponent("/enforce/relay")
        let payload: Parameters = [
            "audit_id": auditId,
            "severity": severity
        ]

        AF.request(url,
                   method: .post,
                   parameters: payload,
                   encoding: JSONEncoding.default)
            .validate()
            .responseDecodable(of: EnforceResponse.self) { response in
                completion(response.result)
            }
    }
}
