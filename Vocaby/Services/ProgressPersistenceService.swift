import Foundation
import SwiftData

struct ProgressPersistenceService {
    func session(
        for dayKey: String,
        targetItemCount: Int = 10,
        in context: ModelContext
    ) throws -> DailySession {
        let descriptor = FetchDescriptor<DailySession>(
            predicate: #Predicate { $0.dayKey == dayKey }
        )

        if let existing = try context.fetch(descriptor).first {
            return existing
        }

        let session = DailySession(dayKey: dayKey, targetItemCount: targetItemCount)
        context.insert(session)
        try context.save()
        return session
    }

    func session(
        for dayKey: String,
        itemIDs: [String],
        reviewItemIDs: Set<String> = [],
        in context: ModelContext
    ) throws -> DailySession {
        let session = try session(for: dayKey, targetItemCount: itemIDs.count, in: context)
        guard session.items.isEmpty else {
            if session.targetItemCount != session.items.count {
                session.targetItemCount = session.items.count
                try context.save()
            }
            return session
        }

        for (position, itemID) in itemIDs.enumerated() {
            let item = DailySessionItem(
                itemID: itemID,
                position: position,
                isReviewFill: reviewItemIDs.contains(itemID)
            )
            context.insert(item)
            session.items.append(item)
        }

        session.targetItemCount = session.items.count
        try context.save()
        return session
    }

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

    func quizResult(
        dayKey: String,
        itemID: String,
        selectedOptionIndex: Int,
        correctOptionIndex: Int,
        in context: ModelContext
    ) throws -> QuizResult {
        let result = try unsavedQuizResult(
            dayKey: dayKey,
            itemID: itemID,
            selectedOptionIndex: selectedOptionIndex,
            correctOptionIndex: correctOptionIndex,
            in: context
        )
        if context.hasChanges { try context.save() }
        return result
    }

    func unsavedQuizResult(
        dayKey: String,
        itemID: String,
        selectedOptionIndex: Int,
        correctOptionIndex: Int,
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
            correctOptionIndex: correctOptionIndex
        )
        context.insert(result)
        return result
    }

    func practiceAttempt(
        runID: String,
        itemID: String,
        level: VocabularyLevel,
        mode: PracticeMode,
        wasCorrect: Bool,
        in context: ModelContext
    ) throws -> PracticeAttemptRecord {
        let attempt = unsavedPracticeAttempt(
            runID: runID, itemID: itemID, level: level, mode: mode, wasCorrect: wasCorrect, in: context
        )
        try context.save()
        return attempt
    }

    func unsavedPracticeAttempt(
        runID: String,
        itemID: String,
        level: VocabularyLevel,
        mode: PracticeMode,
        wasCorrect: Bool,
        in context: ModelContext
    ) -> PracticeAttemptRecord {
        let attempt = PracticeAttemptRecord(
            runID: runID,
            itemID: itemID,
            level: level,
            mode: mode,
            wasCorrect: wasCorrect
        )
        context.insert(attempt)
        return attempt
    }

    private static func quizResultID(dayKey: String, itemID: String) -> String {
        "\(dayKey)#\(itemID)"
    }
}
