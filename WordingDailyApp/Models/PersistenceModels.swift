import Foundation
import SwiftData

@Model
final class WordProgress {
    @Attribute(.unique) var itemID: String
    var levelRawValue: String
    var isSaved: Bool
    var correctCount: Int
    var dueDayKey: String?
    var wrongCount: Int
    var masteredAt: Date?
    var updatedAt: Date

    init(
        itemID: String,
        level: VocabularyLevel,
        isSaved: Bool = false,
        correctCount: Int = 0,
        dueDayKey: String? = nil,
        wrongCount: Int = 0,
        masteredAt: Date? = nil,
        updatedAt: Date = Date()
    ) {
        self.itemID = itemID
        self.levelRawValue = level.rawValue
        self.isSaved = isSaved
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

@Model
final class DailySessionItem {
    var itemID: String
    var position: Int
    var answeredAt: Date?
    var selectedOptionIndex: Int?
    var wasCorrect: Bool?

    init(
        itemID: String,
        position: Int,
        answeredAt: Date? = nil,
        selectedOptionIndex: Int? = nil,
        wasCorrect: Bool? = nil
    ) {
        self.itemID = itemID
        self.position = position
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
