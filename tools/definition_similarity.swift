import Foundation
import NaturalLanguage

private struct Query: Decodable {
    let id: String
    let left: String
    let right: String
}

private struct Result: Encodable {
    let id: String
    let distance: Double
}

guard let embedding = NLEmbedding.sentenceEmbedding(for: .english) else {
    FileHandle.standardError.write(Data("English sentence embedding is unavailable.\n".utf8))
    exit(1)
}

let decoder = JSONDecoder()
let encoder = JSONEncoder()

while let line = readLine() {
    guard !line.isEmpty else { continue }
    do {
        let query = try decoder.decode(Query.self, from: Data(line.utf8))
        let distance = query.right.isEmpty
            ? 2.0
            : Double(embedding.distance(between: query.left, and: query.right))
        let data = try encoder.encode(Result(id: query.id, distance: distance))
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data("\n".utf8))
    } catch {
        FileHandle.standardError.write(Data("Invalid similarity query: \(error)\n".utf8))
        exit(1)
    }
}
