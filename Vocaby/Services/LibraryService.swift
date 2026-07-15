import Foundation

enum LibraryScope: Hashable {
    case learned
    case saved
}

struct LibraryListItem: Identifiable, Equatable {
    var id: String { seedItem.id }

    let seedItem: VocabularySeedItem
    let progress: WordProgress?
}

struct LibraryLevelSummary: Equatable, Identifiable {
    let level: VocabularyLevel
    let learnedCount: Int
    let totalCount: Int

    var id: VocabularyLevel { level }

    var progress: Double {
        guard totalCount > 0 else { return 0 }
        return Double(learnedCount) / Double(totalCount)
    }
}

struct LibraryService {
    func levelSummaries(
        from seedItems: [VocabularySeedItem],
        quizResults: [QuizResult],
        contentLanguageCode: String,
        supportLanguageCode: String
    ) -> [LibraryLevelSummary] {
        let learnedIDs = Set(quizResults.map(\.itemID))
        let eligibleItems = seedItems.filter { item in
            item.contentLanguageCode == contentLanguageCode
                && item.supportLanguageCodes.contains(supportLanguageCode)
        }

        return VocabularyLevel.allCases.map { level in
            let levelItems = eligibleItems.filter { $0.level == level }
            let learnedCount = levelItems.lazy.filter { learnedIDs.contains($0.id) }.count
            return LibraryLevelSummary(
                level: level,
                learnedCount: learnedCount,
                totalCount: levelItems.count
            )
        }
    }

    func items(
        from seedItems: [VocabularySeedItem],
        progressRows: [WordProgress],
        quizResults: [QuizResult],
        scope: LibraryScope,
        query: String,
        contentLanguageCode: String,
        supportLanguageCode: String
    ) -> [LibraryListItem] {
        let progressByID = Dictionary(progressRows.map { ($0.itemID, $0) }, uniquingKeysWith: { first, _ in first })
        let learnedIDs = Set(quizResults.map(\.itemID))
        let savedIDs = Set(progressRows.filter(\.isSaved).map(\.itemID))
        let eligibleIDs = scope == .learned ? learnedIDs : savedIDs
        let normalizedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()

        return seedItems
            .filter { item in
                eligibleIDs.contains(item.id)
                    && item.contentLanguageCode == contentLanguageCode
                    && item.supportLanguageCodes.contains(supportLanguageCode)
                    && matchesSearch(item, query: normalizedQuery, supportLanguageCode: supportLanguageCode)
            }
            .sorted { lhs, rhs in
                if lhs.sortOrder == rhs.sortOrder {
                    return lhs.id < rhs.id
                }
                return lhs.sortOrder < rhs.sortOrder
            }
            .map { LibraryListItem(seedItem: $0, progress: progressByID[$0.id]) }
    }

    private func matchesSearch(
        _ item: VocabularySeedItem,
        query: String,
        supportLanguageCode: String
    ) -> Bool {
        guard !query.isEmpty else {
            return true
        }

        let searchableText = [
            item.plainExpression,
            item.upgradedExpression
        ] + item.pronunciations.map(\.ipa) + item.senses.flatMap { sense in
            [sense.meaning["en"] ?? "", sense.meaning[supportLanguageCode] ?? ""]
        }

        return searchableText.contains { $0.lowercased().contains(query) }
    }
}
