import Foundation
import SwiftData

@Model
final class WordProgress {
    @Attribute(.unique) var itemID: String
    var levelRawValue: String
    var isSaved: Bool
    var firstSeenAt: Date?
    var lastReviewedAt: Date?
    var correctCount: Int
    var dueDayKey: String?
    var wrongCount: Int
    var masteredAt: Date?
    var updatedAt: Date

    init(
        itemID: String,
        level: VocabularyLevel,
        isSaved: Bool = false,
        firstSeenAt: Date? = nil,
        lastReviewedAt: Date? = nil,
        correctCount: Int = 0,
        dueDayKey: String? = nil,
        wrongCount: Int = 0,
        masteredAt: Date? = nil,
        updatedAt: Date = Date()
    ) {
        self.itemID = itemID
        self.levelRawValue = level.rawValue
        self.isSaved = isSaved
        self.firstSeenAt = firstSeenAt
        self.lastReviewedAt = lastReviewedAt
        self.correctCount = correctCount
        self.dueDayKey = dueDayKey
        self.wrongCount = wrongCount
        self.masteredAt = masteredAt
        self.updatedAt = updatedAt
    }
}

@Model
final class DailySession {
    @Attribute(.unique) var dayKey: String
    var targetItemCount: Int
    var createdAt: Date
    var completedAt: Date?
    @Relationship(deleteRule: .cascade) var items: [DailySessionItem]

    init(dayKey: String, targetItemCount: Int = 10, createdAt: Date = Date(), completedAt: Date? = nil) {
        self.dayKey = dayKey
        self.targetItemCount = targetItemCount
        self.createdAt = createdAt
        self.completedAt = completedAt
        self.items = []
    }
}

extension DailySession {
    var completedItemCount: Int {
        items.filter { $0.answeredAt != nil }.count
    }

    var correctItemCount: Int {
        items.filter { $0.wasCorrect == true }.count
    }

    func scheduledReviewCount(from progressRows: [WordProgress]) -> Int {
        let completedItemIDs = Set(items.compactMap { $0.answeredAt == nil ? nil : $0.itemID })
        return Set(progressRows.compactMap { progress -> String? in
            guard completedItemIDs.contains(progress.itemID),
                  progress.dueDayKey != nil,
                  progress.masteredAt == nil else {
                return nil
            }

            return progress.itemID
        }).count
    }
}

@Model
final class DailySessionItem {
    var itemID: String
    var position: Int
    var isReviewFill: Bool = false
    var answeredAt: Date?
    var selectedOptionIndex: Int?
    var wasCorrect: Bool?

    init(
        itemID: String,
        position: Int,
        isReviewFill: Bool = false,
        answeredAt: Date? = nil,
        selectedOptionIndex: Int? = nil,
        wasCorrect: Bool? = nil
    ) {
        self.itemID = itemID
        self.position = position
        self.isReviewFill = isReviewFill
        self.answeredAt = answeredAt
        self.selectedOptionIndex = selectedOptionIndex
        self.wasCorrect = wasCorrect
    }
}

@Model
final class QuizResult {
    @Attribute(.unique) var id: String
    var dayKey: String
    var itemID: String
    var selectedOptionIndex: Int
    var correctOptionIndex: Int
    var answeredAt: Date
    var wasCorrect: Bool

    init(
        dayKey: String,
        itemID: String,
        selectedOptionIndex: Int,
        correctOptionIndex: Int,
        answeredAt: Date = Date()
    ) {
        self.id = "\(dayKey)#\(itemID)"
        self.dayKey = dayKey
        self.itemID = itemID
        self.selectedOptionIndex = selectedOptionIndex
        self.correctOptionIndex = correctOptionIndex
        self.answeredAt = answeredAt
        self.wasCorrect = selectedOptionIndex == correctOptionIndex
    }
}
