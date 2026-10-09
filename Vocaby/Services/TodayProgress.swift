import Foundation

/// 今天的進度:完成數、總數、下一個要學的項目。畫面與 widget 共用,不依賴任何 View 狀態。
struct TodayProgress: Equatable {
    let completed: Int
    let total: Int
    let nextItemID: String?

    init(session: DailySession?, dailyGoal: Int) {
        let items = (session?.items ?? []).sorted { $0.position < $1.position }
        completed = session?.completedItemCount ?? 0
        total = items.isEmpty ? dailyGoal : items.count
        nextItemID = items.first { $0.answeredAt == nil }?.itemID
    }
}

extension WidgetSnapshot {
    /// 由 session 與種子算出 widget 內容;給定相同輸入就得到相同結果,與呼叫順序無關。
    static func today(
        dayKey: String,
        session: DailySession?,
        seedItems: [VocabularySeedItem],
        streakCount: Int,
        dailyGoal: Int,
        generatedAt: Date
    ) -> WidgetSnapshot {
        let progress = TodayProgress(session: session, dailyGoal: dailyGoal)
        let seedByID = Dictionary(uniqueKeysWithValues: seedItems.map { ($0.id, $0) })

        return WidgetSnapshot(
            dayKey: dayKey,
            progressCompleted: progress.completed,
            progressTotal: progress.total,
            streakCount: streakCount,
            displayExpression: progress.nextItemID.flatMap { seedByID[$0] }.map {
                WidgetSnapshotExpression(
                    itemID: $0.id,
                    plainExpression: $0.plainExpression,
                    upgradedExpression: $0.upgradedExpression
                )
            },
            generatedAt: generatedAt
        )
    }
}
