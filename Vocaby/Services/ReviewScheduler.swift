import Foundation

enum ReviewAnswerContext {
    case dailyPractice
    case review
}

extension DailySessionItem {
    var reviewAnswerContext: ReviewAnswerContext {
        isReviewFill ? .review : .dailyPractice
    }
}

struct ReviewScheduler {
    private let dayKeyService: DayKeyService
    private let sm2: SM2

    init(dayKeyService: DayKeyService = DayKeyService(), sm2: SM2 = SM2()) {
        self.dayKeyService = dayKeyService
        self.sm2 = sm2
    }

    func applyAnswer(
        to progress: WordProgress,
        wasCorrect: Bool,
        answeredAt: Date,
        context: ReviewAnswerContext
    ) {
        applyAnswer(
            to: progress,
            quality: wasCorrect ? 5 : 1,
            answeredAt: answeredAt,
            context: context
        )
    }

    func applyAnswer(
        to progress: WordProgress,
        quality: Int,
        answeredAt: Date,
        context: ReviewAnswerContext
    ) {
        if progress.firstSeenAt == nil {
            progress.firstSeenAt = answeredAt
        }
        progress.lastReviewedAt = answeredAt
        progress.updatedAt = answeredAt

        let clampedQuality = min(5, max(0, quality))
        let wasCorrect = clampedQuality >= 3
        if wasCorrect {
            progress.correctCount += 1
        } else {
            progress.wrongCount += 1
        }

        let result = sm2.schedule(
            state: SM2State(
                easeFactor: progress.easeFactor,
                repetitionCount: progress.repetitionCount,
                intervalDays: progress.intervalDays
            ),
            quality: clampedQuality,
            answeredAt: answeredAt
        )
        progress.easeFactor = result.state.easeFactor
        progress.repetitionCount = result.state.repetitionCount
        progress.intervalDays = result.state.intervalDays
        progress.nextReviewAt = result.nextReviewAt
        progress.lastQuality = clampedQuality
        progress.masteredAt = result.isMastered ? answeredAt : nil
        progress.dueDayKey = result.isMastered ? nil : dayKeyService.dayKey(for: result.nextReviewAt)
    }

    func dueItems(from progressRows: [WordProgress], on dayKey: String, limit: Int = 20) -> [WordProgress] {
        Array(progressRows
            .filter { progress in
                guard let dueDayKey = progress.dueDayKey else {
                    return false
                }

                return progress.masteredAt == nil && dueDayKey <= dayKey
            }
            .sorted { lhs, rhs in
                let lhsDueDayKey = lhs.dueDayKey ?? ""
                let rhsDueDayKey = rhs.dueDayKey ?? ""

                if lhsDueDayKey != rhsDueDayKey {
                    return lhsDueDayKey < rhsDueDayKey
                }

                if lhs.wrongCount != rhs.wrongCount {
                    return lhs.wrongCount > rhs.wrongCount
                }

                return lhs.itemID < rhs.itemID
            }
            .prefix(max(0, limit)))
    }

    func dueItems(from progressRows: [WordProgress], at date: Date, limit: Int = 20) -> [WordProgress] {
        let dayKey = dayKeyService.dayKey(for: date)
        return Array(progressRows
            .filter { progress in
                guard progress.masteredAt == nil,
                      let dueDayKey = progress.dueDayKey,
                      dueDayKey <= dayKey else {
                    return false
                }

                // Legacy rows only have a day key. New SM-2 rows also carry an
                // exact timestamp so failed cards do not reappear before the
                // required ten-minute retry delay.
                return progress.nextReviewAt.map { $0 <= date } ?? true
            }
            .sorted(by: dueSort)
            .prefix(max(0, limit)))
    }

    func dueCount(from progressRows: [WordProgress], on dayKey: String) -> Int {
        allDueItems(from: progressRows, on: dayKey).count
    }

    func dueCount(from progressRows: [WordProgress], at date: Date) -> Int {
        allDueItems(from: progressRows, at: date).count
    }

    func allDueItems(from progressRows: [WordProgress], on dayKey: String) -> [WordProgress] {
        dueItems(from: progressRows, on: dayKey, limit: progressRows.count)
    }

    func allDueItems(from progressRows: [WordProgress], at date: Date) -> [WordProgress] {
        dueItems(from: progressRows, at: date, limit: progressRows.count)
    }

    private func dueSort(_ lhs: WordProgress, _ rhs: WordProgress) -> Bool {
        let lhsDate = lhs.nextReviewAt ?? .distantPast
        let rhsDate = rhs.nextReviewAt ?? .distantPast
        if lhsDate != rhsDate { return lhsDate < rhsDate }
        if lhs.wrongCount != rhs.wrongCount { return lhs.wrongCount > rhs.wrongCount }
        return lhs.itemID < rhs.itemID
    }

}
