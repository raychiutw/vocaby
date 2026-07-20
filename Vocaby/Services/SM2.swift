import Foundation

struct SM2State: Equatable {
    var easeFactor: Double = 2.5
    var repetitionCount: Int = 0
    var intervalDays: Int = 0
}

struct SM2Result: Equatable {
    let state: SM2State
    let nextReviewAt: Date
    let isMastered: Bool
}

struct SM2 {
    static let minimumEaseFactor = 1.3

    func schedule(
        state: SM2State,
        quality rawQuality: Int,
        answeredAt: Date,
        calendar: Calendar = .current
    ) -> SM2Result {
        let quality = min(5, max(0, rawQuality))
        let difference = Double(5 - quality)
        let easeFactor = max(
            Self.minimumEaseFactor,
            state.easeFactor + 0.1 - difference * (0.08 + difference * 0.02)
        )

        guard quality >= 3 else {
            return SM2Result(
                state: SM2State(easeFactor: easeFactor, repetitionCount: 0, intervalDays: 0),
                nextReviewAt: answeredAt.addingTimeInterval(10 * 60),
                isMastered: false
            )
        }

        let repetitions = state.repetitionCount + 1
        let intervalDays: Int
        switch repetitions {
        case 1:
            intervalDays = 1
        case 2:
            intervalDays = 6
        default:
            intervalDays = max(1, Int((Double(max(1, state.intervalDays)) * easeFactor).rounded()))
        }

        let nextReviewAt = calendar.date(byAdding: .day, value: intervalDays, to: answeredAt)
            ?? answeredAt.addingTimeInterval(TimeInterval(intervalDays * 86_400))

        return SM2Result(
            state: SM2State(
                easeFactor: easeFactor,
                repetitionCount: repetitions,
                intervalDays: intervalDays
            ),
            nextReviewAt: nextReviewAt,
            isMastered: repetitions >= 4 && intervalDays >= 21
        )
    }
}
