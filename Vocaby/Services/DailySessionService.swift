import Foundation
import SwiftData

/// 今天的 session 生命週期:取得或建立、學完後追加。
/// 新字的 firstSeenAt 不在這裡標記;由 ReviewScheduler 在答題時才設定。
/// 建立時合成一次 save();失敗則 rollback,不會留下空的 session。
/// 注意:rollback 作用於整個傳入的 ModelContext,會一併丟掉呼叫端在同一個 context 上尚未存檔的修改。
struct DailySessionService {
    static let extraBatchSize = 10

    private let planner: DailyPlanner

    init(planner: DailyPlanner = DailyPlanner()) {
        self.planner = planner
    }

    /// 今天的 session:已有就回傳(內容不替換),沒有就依計畫建立。
    /// 沒有任何可學的字時回傳 nil,而且不會建立空的 session。
    func sessionForToday(
        dayKey: String,
        seed: [VocabularySeedItem],
        progressRows: [WordProgress],
        preferences: UserPreferences,
        now: Date,
        in context: ModelContext
    ) throws -> DailySession? {
        do {
            let descriptor = FetchDescriptor<DailySession>(predicate: #Predicate { $0.dayKey == dayKey })
            let existing = try context.fetch(descriptor).first
            if let existing, !existing.items.isEmpty {
                return existing
            }

            let plan = planner.plan(seed: seed, progressRows: progressRows, preferences: preferences, now: now)
            guard !plan.itemIDs.isEmpty else { return nil }

            // 已有但是空的 session(舊版本可能留下)就補滿它,不另建一個
            let session = existing ?? DailySession(dayKey: dayKey, targetItemCount: plan.itemIDs.count, createdAt: now)
            if existing == nil { context.insert(session) }
            for (position, itemID) in plan.itemIDs.enumerated() {
                let item = DailySessionItem(
                    itemID: itemID,
                    position: position,
                    isReviewFill: plan.reviewItemIDs.contains(itemID)
                )
                context.insert(item)
                session.items.append(item)
            }
            session.targetItemCount = session.items.count
            session.completedAt = nil  // 補滿的是舊版本留下的空 session,現在有未作答的項目
            try context.save()
            return session
        } catch {
            context.rollback()
            throw error
        }
    }

    /// 學完一輪後再追加最多 10 個還沒看過、也不在今天 session 內的字,並重新開啟 session。
    /// 有追加時回傳 true。
    @discardableResult
    func appendExtraItems(
        to session: DailySession,
        seed: [VocabularySeedItem],
        progressRows: [WordProgress],
        level: VocabularyLevel,
        in context: ModelContext
    ) throws -> Bool {
        let usedIDs = Set(session.items.map(\.itemID))
        let learnedIDs = Set(progressRows.compactMap { $0.firstSeenAt == nil ? nil : $0.itemID })
        let extraItems = seed
            .filter { $0.level == level && !usedIDs.contains($0.id) && !learnedIDs.contains($0.id) }
            .prefix(Self.extraBatchSize)
        guard !extraItems.isEmpty else { return false }

        do {
            let startPosition = session.items.map(\.position).max().map { $0 + 1 } ?? 0
            for (offset, item) in extraItems.enumerated() {
                session.items.append(DailySessionItem(itemID: item.id, position: startPosition + offset))
            }
            session.targetItemCount = session.items.count
            session.completedAt = nil
            try context.save()
            return true
        } catch {
            context.rollback()
            throw error
        }
    }
}
