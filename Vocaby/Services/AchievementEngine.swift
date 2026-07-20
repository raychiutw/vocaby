import Foundation

enum AchievementID: String, CaseIterable, Sendable {
    case firstStudy
    case streak3
    case streak7
    case streak30
    case learn100
    case learn500
    case master100
    case save10
    case perfectPractice
    case day50
}

struct AchievementMetrics: Equatable, Sendable {
    var learnedCount: Int
    var masteredCount: Int
    var savedCount: Int
    var currentStreak: Int
    var maximumDailyCount: Int
    var hasPerfectPractice: Bool
}

struct AchievementEngine {
    func newlyUnlocked(
        metrics: AchievementMetrics,
        existing: Set<AchievementID>
    ) -> [AchievementID] {
        AchievementID.allCases.filter { id in
            !existing.contains(id) && isUnlocked(id, metrics: metrics)
        }
    }

    func isUnlocked(_ id: AchievementID, metrics: AchievementMetrics) -> Bool {
        switch id {
        case .firstStudy: metrics.learnedCount >= 1
        case .streak3: metrics.currentStreak >= 3
        case .streak7: metrics.currentStreak >= 7
        case .streak30: metrics.currentStreak >= 30
        case .learn100: metrics.learnedCount >= 100
        case .learn500: metrics.learnedCount >= 500
        case .master100: metrics.masteredCount >= 100
        case .save10: metrics.savedCount >= 10
        case .perfectPractice: metrics.hasPerfectPractice
        case .day50: metrics.maximumDailyCount >= 50
        }
    }
}

extension AchievementMetrics {
    static func make(
        progressRows: [WordProgress],
        sessions: [DailySession],
        attempts: [PracticeAttemptRecord],
        calendar: Calendar = .current,
        now: Date = Date()
    ) -> AchievementMetrics {
        let learned = progressRows.filter { $0.firstSeenAt != nil }.count
        let mastered = progressRows.filter { $0.masteredAt != nil }.count
        let saved = progressRows.filter(\.isSaved).count
        let maximumDailyCount = sessions.map(\.completedItemCount).max() ?? 0
        let completedDays = Set(sessions.filter { $0.completedItemCount > 0 }.map(\.dayKey))
        let streak = currentStreak(completedDays: completedDays, calendar: calendar, now: now)
        let groupedAttempts = Dictionary(grouping: attempts, by: \.runID)
        let hasPerfectPractice = groupedAttempts.values.contains { run in
            !run.isEmpty && run.allSatisfy(\.wasCorrect)
        }
        return AchievementMetrics(
            learnedCount: learned,
            masteredCount: mastered,
            savedCount: saved,
            currentStreak: streak,
            maximumDailyCount: maximumDailyCount,
            hasPerfectPractice: hasPerfectPractice
        )
    }

    private static func currentStreak(
        completedDays: Set<String>,
        calendar: Calendar,
        now: Date
    ) -> Int {
        let dayKeyService = DayKeyService(calendar: calendar)
        var cursor = calendar.startOfDay(for: now)
        if !completedDays.contains(dayKeyService.dayKey(for: cursor)),
           let yesterday = calendar.date(byAdding: .day, value: -1, to: cursor) {
            cursor = yesterday
        }
        var streak = 0
        while completedDays.contains(dayKeyService.dayKey(for: cursor)) {
            streak += 1
            guard let previous = calendar.date(byAdding: .day, value: -1, to: cursor) else { break }
            cursor = previous
        }
        return streak
    }
}
