import Foundation
import FoundationModels
import Translation

private struct TextRequest: Codable {
    let id: String
    let text: String
}

private struct TextResponse: Codable {
    let id: String
    let text: String
}

private struct EnrichmentBatch: Codable {
    let batchID: String
    let items: [EnrichmentItem]
}

private struct EnrichmentItem: Codable {
    let id: String
    let target: String
    let partOfSpeech: String
    let meaning: String
    let plainCandidates: [String]
    let exampleCandidate: String
}

private struct EnrichmentResponse: Codable {
    let batchID: String
    let items: [ReviewedEnrichment]
}

@Generable
struct ReviewedEnrichment: Codable {
    let id: String
    @Guide(description: "A natural simpler English equivalent, at most eight words, never a definition, target, or inflected target form")
    let plainExpression: String
    @Guide(description: "One original full English sentence containing the exact target expression")
    let example: String
}

@Generable
struct ReviewedEnrichmentBatch {
    let items: [ReviewedEnrichment]
}

private enum ToolError: Error, LocalizedError {
    case usage
    case unavailable(String)
    case malformedInput(String)

    var errorDescription: String? {
        switch self {
        case .usage:
            return "usage: apple_language_services.swift availability|translate|enrich"
        case .unavailable(let detail), .malformedInput(let detail):
            return detail
        }
    }
}

@main
private struct AppleLanguageServices {
    static func main() async {
        do {
            guard CommandLine.arguments.count == 2 else { throw ToolError.usage }
            switch CommandLine.arguments[1] {
            case "availability":
                try await availability()
            case "translate":
                try await translate()
            case "enrich":
                try await enrich()
            default:
                throw ToolError.usage
            }
        } catch {
            FileHandle.standardError.write(Data("error: \(error.localizedDescription)\n".utf8))
            exit(1)
        }
    }

    private static let decoder = JSONDecoder()
    private static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return encoder
    }()

    private static func inputLines() throws -> [String] {
        let data = FileHandle.standardInput.readDataToEndOfFile()
        guard let input = String(data: data, encoding: .utf8) else {
            throw ToolError.malformedInput("stdin is not UTF-8")
        }
        return input.split(whereSeparator: \.isNewline).map(String.init)
    }

    private static func write<T: Encodable>(_ value: T) throws {
        var data = try encoder.encode(value)
        data.append(0x0A)
        FileHandle.standardOutput.write(data)
    }

    private static func availability() async throws {
        let source = Locale.Language(identifier: "en")
        let target = Locale.Language(identifier: "zh-Hant")
        let translation = await LanguageAvailability().status(from: source, to: target)
        print("translation=\(translation) foundationModels=\(SystemLanguageModel.default.availability)")
    }

    private static func translate() async throws {
        let source = Locale.Language(identifier: "en")
        let target = Locale.Language(identifier: "zh-Hant")
        let status = await LanguageAvailability().status(from: source, to: target)
        guard status == .installed else {
            throw ToolError.unavailable("English to Traditional Chinese translation is not installed")
        }
        let requests = try inputLines().map {
            try decoder.decode(TextRequest.self, from: Data($0.utf8))
        }
        let session = TranslationSession(installedSource: source, target: target)
        for start in stride(from: 0, to: requests.count, by: 100) {
            let chunk = requests[start ..< min(start + 100, requests.count)]
            let responses = try await session.translations(
                from: chunk.map {
                    TranslationSession.Request(sourceText: $0.text, clientIdentifier: $0.id)
                }
            )
            for response in responses {
                guard let id = response.clientIdentifier else {
                    throw ToolError.malformedInput("translation response omitted its ID")
                }
                try write(TextResponse(id: id, text: response.targetText))
            }
        }
    }

    private static func enrich() async throws {
        guard SystemLanguageModel.default.isAvailable else {
            throw ToolError.unavailable("Foundation Models is not available")
        }
        let batches = try inputLines().map {
            try decoder.decode(EnrichmentBatch.self, from: Data($0.utf8))
        }
        for batch in batches {
            let payload = String(data: try encoder.encode(batch.items), encoding: .utf8)!
            let session = LanguageModelSession(instructions: """
                You edit English vocabulary content for Taiwan learners. Return JSON only.
                Preserve every id and target exactly. For each input produce plainExpression,
                and example. plainExpression is a natural simpler equivalent of at most eight
                words, never a dictionary definition. plainExpression must never contain target or any inflected target form.
                If plainCandidates is nonempty, choose the meaning-aligned value from that list. The example MUST contain the exact
                target expression and use its supplied part of speech and meaning. Never replace
                target with plainExpression. Write one original natural full sentence under 18
                words. Use exampleCandidate as sense guidance when it is present, but rewrite it
                naturally rather than copying it. Return exactly one item per input in the same
                order.
                """)
            let response = try await session.respond(
                to: "Edit these records and return exactly \(batch.items.count) items in the same order:\n\(payload)",
                generating: ReviewedEnrichmentBatch.self
            )
            try write(
                EnrichmentResponse(
                    batchID: batch.batchID,
                    items: response.content.items
                )
            )
        }
    }

}
