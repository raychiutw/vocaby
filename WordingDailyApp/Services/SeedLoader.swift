import Foundation

enum SeedLoaderError: Error, Equatable {
    case missingResource
}

enum SeedValidationError: Error, Equatable {
    case duplicateID(String)
    case missingRequiredField(String)
    case invalidPrimarySense(String)
    case invalidPronunciationReference(String)
    case invalidCorrectOptionIndex(String)
    case sortOrderNotAscending(VocabularyLevel)
}

struct SeedLoader {
    private let bundle: Bundle

    init(bundle: Bundle = Bundle(for: BundleToken.self)) {
        self.bundle = bundle
    }

    func loadBundledSeed() throws -> [VocabularySeedItem] {
        guard let url = bundle.url(forResource: "VocabularySeed", withExtension: "json") else {
            throw SeedLoaderError.missingResource
        }

        let data = try Data(contentsOf: url)
        let items = try JSONDecoder().decode([VocabularySeedItem].self, from: data)
        try SeedValidator.validate(items)
        return items
    }

    static let sampleItems: [VocabularySeedItem] = [
        VocabularySeedItem(
            id: "sample-basic-001",
            level: .basic,
            sortOrder: 1,
            contentLanguageCode: "en",
            supportLanguageCodes: ["zh-Hant"],
            plainExpression: "very good",
            upgradedExpression: "excellent",
            primarySenseID: "sample-basic-001-sense-1",
            pronunciations: [
                VocabularyPronunciation(
                    id: "sample-basic-001-pronunciation-1",
                    ipa: "ˈɛksələnt",
                    speechLocale: "en-US",
                    region: "US"
                )
            ],
            senses: [
                VocabularySense(
                    id: "sample-basic-001-sense-1",
                    partOfSpeech: .adjective,
                    meaning: [
                        "en": "A stronger, cleaner way to say very good.",
                        "zh-Hant": "比 very good 更精準，用來稱讚表現或品質。"
                    ],
                    example: VocabularyExample(
                        text: "Your summary was excellent.",
                        translation: ["zh-Hant": "你的摘要寫得很出色。"]
                    ),
                    pronunciationIDs: ["sample-basic-001-pronunciation-1"]
                )
            ],
            quiz: VocabularyQuiz(
                prompt: [
                    "en": "Which expression best upgrades very good?",
                    "zh-Hant": "哪個表達最適合替換 very good？"
                ],
                options: ["excellent", "very okay", "not bad", "maybe good"],
                correctOptionIndex: 0
            )
        ),
        VocabularySeedItem(
            id: "sample-basic-002",
            level: .basic,
            sortOrder: 2,
            contentLanguageCode: "en",
            supportLanguageCodes: ["zh-Hant"],
            plainExpression: "help me",
            upgradedExpression: "give me a hand",
            primarySenseID: "sample-basic-002-sense-1",
            pronunciations: [
                VocabularyPronunciation(
                    id: "sample-basic-002-pronunciation-1",
                    ipa: "ɡɪv mi ə hænd",
                    speechLocale: "en-US",
                    region: "US"
                )
            ],
            senses: [
                VocabularySense(
                    id: "sample-basic-002-sense-1",
                    partOfSpeech: .phrase,
                    meaning: [
                        "en": "A friendly request for help.",
                        "zh-Hant": "自然、口語的請人幫忙說法。"
                    ],
                    example: VocabularyExample(
                        text: "Could you give me a hand with this?",
                        translation: ["zh-Hant": "你可以幫我處理這個嗎？"]
                    ),
                    pronunciationIDs: ["sample-basic-002-pronunciation-1"]
                )
            ],
            quiz: VocabularyQuiz(
                prompt: [
                    "en": "Which expression best upgrades help me?",
                    "zh-Hant": "哪個表達最適合替換 help me？"
                ],
                options: ["give me a hand", "hand me a give", "helping maybe", "good help"],
                correctOptionIndex: 0
            )
        )
    ]
}

enum SeedValidator {
    static func validate(_ items: [VocabularySeedItem]) throws {
        var seenIDs = Set<String>()
        var lastSortOrderByLevel: [VocabularyLevel: Int] = [:]

        for item in items {
            guard seenIDs.insert(item.id).inserted else {
                throw SeedValidationError.duplicateID(item.id)
            }

            try validateRequiredFields(item)

            guard item.quiz.options.indices.contains(item.quiz.correctOptionIndex) else {
                throw SeedValidationError.invalidCorrectOptionIndex(item.id)
            }

            if let previousSortOrder = lastSortOrderByLevel[item.level],
               item.sortOrder <= previousSortOrder {
                throw SeedValidationError.sortOrderNotAscending(item.level)
            }
            lastSortOrderByLevel[item.level] = item.sortOrder
        }
    }

    private static func validateRequiredFields(_ item: VocabularySeedItem) throws {
        let requiredValues = [
            item.id,
            item.contentLanguageCode,
            item.plainExpression,
            item.upgradedExpression,
            item.primarySenseID
        ]

        if requiredValues.contains(where: { $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) {
            throw SeedValidationError.missingRequiredField(item.id)
        }

        if item.supportLanguageCodes.isEmpty ||
            item.supportLanguageCodes.contains(where: { $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) ||
            item.quiz.options.count < 2 ||
            item.quiz.options.contains(where: { $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) {
            throw SeedValidationError.missingRequiredField(item.id)
        }

        let pronunciationIDs = item.pronunciations.map(\.id)
        guard !pronunciationIDs.isEmpty,
              Set(pronunciationIDs).count == pronunciationIDs.count,
              item.pronunciations.allSatisfy({ pronunciation in
                  !pronunciation.id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
                      !pronunciation.ipa.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
                      pronunciation.ipa == pronunciation.ipa
                          .trimmingCharacters(in: CharacterSet(charactersIn: "/[] ")) &&
                      pronunciation.speechLocale.hasPrefix("en-")
              }) else {
            throw SeedValidationError.missingRequiredField(item.id)
        }

        let senseIDs = item.senses.map(\.id)
        guard (1...3).contains(senseIDs.count),
              Set(senseIDs).count == senseIDs.count else {
            throw SeedValidationError.missingRequiredField(item.id)
        }
        guard senseIDs.contains(item.primarySenseID) else {
            throw SeedValidationError.invalidPrimarySense(item.id)
        }

        let knownPronunciationIDs = Set(pronunciationIDs)
        for sense in item.senses {
            let references = Set(sense.pronunciationIDs)
            guard !references.isEmpty,
                  references.count == sense.pronunciationIDs.count,
                  references.isSubset(of: knownPronunciationIDs) else {
                throw SeedValidationError.invalidPronunciationReference(item.id)
            }

            guard !sense.id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  sense.meaning["en"]?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false,
                  !sense.example.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                throw SeedValidationError.missingRequiredField(item.id)
            }

            for languageCode in item.supportLanguageCodes {
                guard sense.meaning[languageCode]?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false,
                      sense.example.translation[languageCode]?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false else {
                    throw SeedValidationError.missingRequiredField(item.id)
                }
            }
        }

        for languageCode in item.supportLanguageCodes {
            guard item.quiz.prompt[languageCode]?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false else {
                throw SeedValidationError.missingRequiredField(item.id)
            }
        }
    }
}

private final class BundleToken {}
