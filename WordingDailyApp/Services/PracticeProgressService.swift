import Foundation

struct VocabularyPracticeProgress: Equatable {
    let correctItemCount: Int
    let totalItemCount: Int
}

struct PracticeProgressSummary {
    let total: VocabularyPracticeProgress
    private let levelProgress: [VocabularyLevel: VocabularyPracticeProgress]

    init(total: VocabularyPracticeProgress, levelProgress: [VocabularyLevel: VocabularyPracticeProgress]) {
        self.total = total
        self.levelProgress = levelProgress
    }

    func progress(for level: VocabularyLevel) -> VocabularyPracticeProgress {
        levelProgress[level] ?? VocabularyPracticeProgress(correctItemCount: 0, totalItemCount: 0)
    }
}

struct PracticeProgressService {
    func summary(
        seedItems: [VocabularySeedItem],
        attempts: [PracticeAttemptRecord]
    ) -> PracticeProgressSummary {
        let seedIDs = Set(seedItems.map(\.id))
        let correctIDs = Set(attempts.lazy.filter(\.wasCorrect).map(\.itemID)).intersection(seedIDs)
        let levels: [VocabularyLevel] = [.basic, .intermediate, .advanced]
        let levelProgress = Dictionary(uniqueKeysWithValues: levels.map { level in
            let levelItems = seedItems.filter { $0.level == level }
            return (
                level,
                VocabularyPracticeProgress(
                    correctItemCount: levelItems.filter { correctIDs.contains($0.id) }.count,
                    totalItemCount: levelItems.count
                )
            )
        })

        return PracticeProgressSummary(
            total: VocabularyPracticeProgress(
                correctItemCount: correctIDs.count,
                totalItemCount: seedItems.count
            ),
            levelProgress: levelProgress
        )
    }
}
