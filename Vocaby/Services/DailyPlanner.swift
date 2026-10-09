import Foundation

/// 「今天要學哪些字」:新字優先、不足時補到期複習。
/// 語系、等級、目標數、已看過的字、到期項目的算法都收在這裡,呼叫端只給資料與「現在」。
struct DailyPlanner {
    static let contentLanguageCode = "en"
    static let supportLanguageCode = "zh-Hant"

    private let selection: DailySelectionService
    private let scheduler: ReviewScheduler

    init(
        selection: DailySelectionService = DailySelectionService(),
        scheduler: ReviewScheduler = ReviewScheduler()
    ) {
        self.selection = selection
        self.scheduler = scheduler
    }

    func plan(
        seed: [VocabularySeedItem],
        progressRows: [WordProgress],
        preferences: UserPreferences,
        now: Date
    ) -> DailySelectionResult {
        selection.selectItems(
            from: seed,
            selectedLevel: preferences.selectedLevel,
            contentLanguageCode: Self.contentLanguageCode,
            supportLanguageCode: Self.supportLanguageCode,
            firstSeenItemIDs: Set(progressRows.compactMap { $0.firstSeenAt == nil ? nil : $0.itemID }),
            dueReviewItemIDs: scheduler.allDueItems(from: progressRows, at: now).map(\.itemID),
            targetCount: preferences.dailyGoal
        )
    }
}
