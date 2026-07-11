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
    var primarySenseID: String
    var pronunciations: [VocabularyPronunciation]
    var senses: [VocabularySense]
    var quiz: VocabularyQuiz

    var primarySense: VocabularySense {
        senses.first { $0.id == primarySenseID }!
    }
}

enum VocabularyPartOfSpeech: String, Codable, CaseIterable, Equatable {
    case noun
    case verb
    case adjective
    case adverb
    case preposition
    case conjunction
    case interjection
    case pronoun
    case determiner
    case phrase
}

struct VocabularyPronunciation: Codable, Identifiable, Equatable {
    var id: String
    var ipa: String
    var speechLocale: String
    var region: String?
}

struct VocabularySense: Codable, Identifiable, Equatable {
    var id: String
    var partOfSpeech: VocabularyPartOfSpeech
    var meaning: [String: String]
    var example: VocabularyExample
    var pronunciationIDs: [String]
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
