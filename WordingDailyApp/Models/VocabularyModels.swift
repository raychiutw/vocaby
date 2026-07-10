import Foundation

enum VocabularyLevel: String, Codable, CaseIterable, Equatable, Hashable {
    case basic
    case intermediate
    case advanced
}

struct VocabularySeedItem: Codable, Identifiable, Equatable {
    var id: String
    var level: VocabularyLevel
    var sortOrder: Int
    var contentLanguageCode: String
    var supportLanguageCodes: [String]
    var plainExpression: String
    var upgradedExpression: String
    var meaning: [String: String]
    var example: VocabularyExample
    var pronunciationText: String
    var quiz: VocabularyQuiz
}

struct VocabularyExample: Codable, Equatable {
    var text: String
    var translation: [String: String]
}

struct VocabularyQuiz: Codable, Equatable {
    var prompt: [String: String]
    var options: [String]
    var correctOptionIndex: Int
}
