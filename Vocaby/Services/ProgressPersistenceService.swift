import Foundation
import SwiftData

struct ProgressPersistenceService {
    func wordProgress(
        for itemID: String,
        level: VocabularyLevel,
        in context: ModelContext
    ) throws -> WordProgress {
        let progress = try unsavedWordProgress(for: itemID, level: level, in: context)
        if context.hasChanges { try context.save() }
        return progress
    }

    /// 與 `wordProgress` 相同但不存檔;給需要把多個步驟合成一次 save 的呼叫端(AnswerRecorder)。
    func unsavedWordProgress(
        for itemID: String,
        level: VocabularyLevel,
        in context: ModelContext
    ) throws -> WordProgress {
        if let existing = try existingWordProgress(for: itemID, in: context) {
            return existing
        }

        let progress = WordProgress(itemID: itemID, level: level)
        context.insert(progress)
        return progress
    }

    func existingWordProgress(
        for itemID: String,
        in context: ModelContext
    ) throws -> WordProgress? {
        let descriptor = FetchDescriptor<WordProgress>(
            predicate: #Predicate { $0.itemID == itemID }
        )
        return try context.fetch(descriptor).first
    }

    /// 不存檔:由 AnswerRecorder 與其他寫入合成一次 save。
    func quizResult(
        dayKey: String,
        itemID: String,
        selectedOptionIndex: Int,
        correctOptionIndex: Int,
        answeredAt: Date,
        in context: ModelContext
    ) throws -> QuizResult {
        let resultID = Self.quizResultID(dayKey: dayKey, itemID: itemID)
        let descriptor = FetchDescriptor<QuizResult>(
            predicate: #Predicate { $0.id == resultID }
        )

        if let existing = try context.fetch(descriptor).first {
            return existing
        }

        let result = QuizResult(
            dayKey: dayKey,
            itemID: itemID,
            selectedOptionIndex: selectedOptionIndex,
            correctOptionIndex: correctOptionIndex,
            answeredAt: answeredAt
        )
        context.insert(result)
        return result
    }

    /// 不存檔:由 AnswerRecorder 與其他寫入合成一次 save。
    func practiceAttempt(
        runID: String,
        itemID: String,
        level: VocabularyLevel,
        mode: PracticeMode,
        wasCorrect: Bool,
        answeredAt: Date,
        in context: ModelContext
    ) -> PracticeAttemptRecord {
        let attempt = PracticeAttemptRecord(
            runID: runID,
            itemID: itemID,
            level: level,
            mode: mode,
            wasCorrect: wasCorrect,
            answeredAt: answeredAt
        )
        context.insert(attempt)
        return attempt
    }

    private static func quizResultID(dayKey: String, itemID: String) -> String {
        "\(dayKey)#\(itemID)"
    }
}
