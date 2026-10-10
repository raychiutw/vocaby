import Foundation
import SwiftData

/// 一次作答要記下的事實,與測驗畫面的型別(QuizAttempt)脫鉤。
struct RecordedAnswer: Equatable {
    let itemID: String
    let level: VocabularyLevel
    let mode: PracticeMode
    let wasCorrect: Bool
    let isFirstAttempt: Bool
    let selectedOptionIndex: Int
    let correctOptionIndex: Int
}

/// 作答來自哪裡。兩種來源的規則不同,由 AnswerRecorder 在內部處理。
enum AnswerSource {
    /// 複習:進度必須已存在;quizResult 以作答當下算出的 dayKey 記;attempt 的 runID 由呼叫端給。
    case review(runID: String, resultDayKey: String)
    /// 自由練習:進度不存在就建立;不記 quizResult。
    case freePractice(runID: String)
}

/// 記錄一次作答:套用排程、寫 quizResult 與 attempt,最後只 save 一次。
/// 任何一步失敗都 rollback 整個 context(含呼叫端在呼叫前對同一 context 做的未存修改),不會留下半筆資料。
/// 保證的是「沒有存進資料庫」;iOS 26 上,已存在的 model 實例仍可能保留記憶體中未存的修改值(iOS 27 會還原)。
struct AnswerRecorder {
    private let persistence: ProgressPersistenceService
    private let scheduler: ReviewScheduler

    init(
        persistence: ProgressPersistenceService = ProgressPersistenceService(),
        scheduler: ReviewScheduler = ReviewScheduler()
    ) {
        self.persistence = persistence
        self.scheduler = scheduler
    }

    func record(
        _ answer: RecordedAnswer,
        from source: AnswerSource,
        at answeredAt: Date,
        in context: ModelContext
    ) throws {
        do {
            if answer.isFirstAttempt {
                try recordFirstAttempt(answer, from: source, at: answeredAt, in: context)
            }

            _ = persistence.practiceAttempt(
                runID: source.attemptRunID,
                itemID: answer.itemID,
                level: answer.level,
                mode: answer.mode,
                wasCorrect: answer.wasCorrect,
                answeredAt: answeredAt,
                in: context
            )
            try context.save()
        } catch {
            context.rollback()
            throw error
        }
    }

    private func recordFirstAttempt(
        _ answer: RecordedAnswer,
        from source: AnswerSource,
        at answeredAt: Date,
        in context: ModelContext
    ) throws {
        let progress: WordProgress
        switch source {
        case .review:
            guard let existing = try persistence.existingWordProgress(for: answer.itemID, in: context) else {
                throw CocoaError(.fileReadCorruptFile)
            }
            progress = existing
        case .freePractice:
            progress = try persistence.unsavedWordProgress(for: answer.itemID, level: answer.level, in: context)
        }

        scheduler.applyAnswer(
            to: progress,
            wasCorrect: answer.wasCorrect,
            answeredAt: answeredAt,
            context: source.scheduleContext
        )

        if let resultDayKey = source.quizResultDayKey {
            _ = try persistence.quizResult(
                dayKey: resultDayKey,
                itemID: answer.itemID,
                selectedOptionIndex: answer.selectedOptionIndex,
                correctOptionIndex: answer.correctOptionIndex,
                answeredAt: answeredAt,
                in: context
            )
        }
    }
}

private extension AnswerSource {
    var attemptRunID: String {
        switch self {
        case .review(let runID, _): runID
        case .freePractice(let runID): runID
        }
    }

    var scheduleContext: ReviewAnswerContext {
        switch self {
        case .review: .review
        case .freePractice: .dailyPractice
        }
    }

    var quizResultDayKey: String? {
        switch self {
        case .review(_, let resultDayKey): resultDayKey
        case .freePractice: nil
        }
    }
}

extension QuizAttempt {
    func recordedAnswer(level: VocabularyLevel) -> RecordedAnswer {
        let indices = question.persistenceIndices(for: submittedAnswer, wasCorrect: wasCorrect)
        return RecordedAnswer(
            itemID: question.itemID,
            level: level,
            mode: question.mode,
            wasCorrect: wasCorrect,
            isFirstAttempt: isFirstAttempt,
            selectedOptionIndex: indices.selected,
            correctOptionIndex: indices.correct
        )
    }
}
