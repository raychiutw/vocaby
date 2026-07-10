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
        if let existing = try existingWordProgress(for: itemID, in: context) {
            return existing
        }

        let progress = WordProgress(itemID: itemID, level: level)
        context.insert(progress)
        try context.save()
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
        try context.save()
        return result
    }

    private static func quizResultID(dayKey: String, itemID: String) -> String {
        "\(dayKey)#\(itemID)"
    }
}
