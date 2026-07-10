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

    init(dayKeyService: DayKeyService = DayKeyService()) {
        self.dayKeyService = dayKeyService
    }

    func applyAnswer(
        to progress: WordProgress,
        wasCorrect: Bool,
        answeredAt: Date,
        context: ReviewAnswerContext
    ) {
        let answeredDayKey = dayKeyService.dayKey(for: answeredAt)
        if progress.firstSeenAt == nil {
            progress.firstSeenAt = answeredAt
        }
        progress.lastReviewedAt = answeredAt
        progress.updatedAt = answeredAt

        if wasCorrect {
            applyCorrectAnswer(to: progress, answeredAt: answeredAt, answeredDayKey: answeredDayKey)
        } else {
            applyWrongAnswer(to: progress, answeredDayKey: answeredDayKey, context: context)
        }
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

    func dueCount(from progressRows: [WordProgress], on dayKey: String) -> Int {
        allDueItems(from: progressRows, on: dayKey).count
    }

    func allDueItems(from progressRows: [WordProgress], on dayKey: String) -> [WordProgress] {
        dueItems(from: progressRows, on: dayKey, limit: progressRows.count)
    }

    private func applyCorrectAnswer(to progress: WordProgress, answeredAt: Date, answeredDayKey: String) {
        progress.correctCount += 1

        guard progress.correctCount < 4 else {
            progress.masteredAt = answeredAt
            progress.dueDayKey = nil
            return
        }

        progress.masteredAt = nil
        progress.dueDayKey = dayKeyService.dayKey(
            byAddingDays: reviewIntervalDays(forCorrectCount: progress.correctCount),
            to: answeredDayKey
        )
    }

    private func applyWrongAnswer(to progress: WordProgress, answeredDayKey: String, context: ReviewAnswerContext) {
        progress.wrongCount += 1
        progress.masteredAt = nil

        switch context {
        case .dailyPractice:
            progress.dueDayKey = answeredDayKey
        case .review:
            progress.dueDayKey = dayKeyService.dayKey(byAddingDays: 1, to: answeredDayKey)
        }
    }

    private func reviewIntervalDays(forCorrectCount correctCount: Int) -> Int {
        switch correctCount {
        case 1:
            return 1
        case 2:
            return 3
        default:
            return 7
        }
    }
}
