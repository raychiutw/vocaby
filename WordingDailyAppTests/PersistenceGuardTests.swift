import SwiftData
import XCTest
@testable import WordingDailyApp

final class PersistenceGuardTests: XCTestCase {
    func testSessionGuardReusesExistingDayKey() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        _ = try service.session(for: "2026-07-10", itemIDs: ["basic-001"], in: context)
        _ = try service.session(for: "2026-07-10", itemIDs: ["basic-001"], in: context)

        let sessions = try context.fetch(FetchDescriptor<DailySession>())
        XCTAssertEqual(sessions.count, 1)
        XCTAssertEqual(sessions.first?.dayKey, "2026-07-10")
        XCTAssertEqual(sessions.first?.targetItemCount, 1)
    }

    func testSessionItemsAreCreatedInSelectionOrder() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        let session = try service.session(
            for: "2026-07-10",
            itemIDs: ["basic-001", "basic-002", "basic-003"],
            reviewItemIDs: ["basic-002"],
            in: context
        )

        let items = session.items.sorted { $0.position < $1.position }
        XCTAssertEqual(session.targetItemCount, 3)
        XCTAssertEqual(items.map(\.itemID), ["basic-001", "basic-002", "basic-003"])
        XCTAssertEqual(items.map(\.position), [0, 1, 2])
        XCTAssertEqual(items.map(\.isReviewFill), [false, true, false])
    }

    func testSessionItemsAreNotReplacedForExistingSession() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        _ = try service.session(
            for: "2026-07-10",
            itemIDs: ["basic-001", "basic-002"],
            in: context
        )
        let existing = try service.session(
            for: "2026-07-10",
            itemIDs: ["basic-003", "basic-004"],
            in: context
        )

        let items = existing.items.sorted { $0.position < $1.position }
        XCTAssertEqual(items.map(\.itemID), ["basic-001", "basic-002"])
    }

    func testCompletionCountsAnsweredAndCorrectSessionItems() {
        let answeredAt = date("2026-07-10T02:00:00Z")
        let session = DailySession(dayKey: "2026-07-10", targetItemCount: 3, completedAt: answeredAt)
        session.items = [
            DailySessionItem(itemID: "basic-001", position: 0, answeredAt: answeredAt, wasCorrect: true),
            DailySessionItem(itemID: "basic-002", position: 1, answeredAt: answeredAt, wasCorrect: false),
            DailySessionItem(itemID: "basic-003", position: 2)
        ]

        XCTAssertEqual(session.completedItemCount, 2)
        XCTAssertEqual(session.correctItemCount, 1)
    }

    func testScheduledReviewCountIncludesOnlyAnsweredUnmasteredSessionItemsWithDueDates() {
        let answeredAt = date("2026-07-10T02:00:00Z")
        let session = DailySession(dayKey: "2026-07-10", targetItemCount: 3, completedAt: answeredAt)
        session.items = [
            DailySessionItem(itemID: "basic-001", position: 0, answeredAt: answeredAt, wasCorrect: true),
            DailySessionItem(itemID: "basic-002", position: 1, answeredAt: answeredAt, wasCorrect: true),
            DailySessionItem(itemID: "basic-003", position: 2)
        ]
        let progressRows = [
            WordProgress(itemID: "basic-001", level: .basic, dueDayKey: "2026-07-11"),
            WordProgress(
                itemID: "basic-002",
                level: .basic,
                dueDayKey: "2026-07-11",
                masteredAt: answeredAt
            ),
            WordProgress(itemID: "basic-003", level: .basic, dueDayKey: "2026-07-11"),
            WordProgress(itemID: "outside-session", level: .basic, dueDayKey: "2026-07-11")
        ]

        XCTAssertEqual(session.scheduledReviewCount(from: progressRows), 1)
    }

    func testWordProgressGuardReusesExistingItemID() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        _ = try service.wordProgress(for: "basic-001", level: .basic, in: context)
        _ = try service.wordProgress(for: "basic-001", level: .basic, in: context)

        let progressRows = try context.fetch(FetchDescriptor<WordProgress>())
        XCTAssertEqual(progressRows.count, 1)
        XCTAssertEqual(progressRows.first?.itemID, "basic-001")
        XCTAssertNil(progressRows.first?.firstSeenAt)
        XCTAssertNil(progressRows.first?.lastReviewedAt)
    }

    func testExistingWordProgressReturnsStoredRowAndDoesNotInsertMissingRow() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()
        let stored = WordProgress(itemID: "basic-001", level: .basic)
        context.insert(stored)
        try context.save()

        let existing = try service.existingWordProgress(for: stored.itemID, in: context)
        let missing = try service.existingWordProgress(for: "missing", in: context)

        XCTAssertEqual(existing?.itemID, stored.itemID)
        XCTAssertNil(missing)
        XCTAssertFalse(context.hasChanges)
        XCTAssertEqual(try context.fetch(FetchDescriptor<WordProgress>()).count, 1)
    }

    func testWordProgressPersistsExplicitTimestamps() throws {
        let context = try makeContext()
        let firstSeenAt = Date(timeIntervalSince1970: 100)
        let lastReviewedAt = Date(timeIntervalSince1970: 200)
        context.insert(WordProgress(
            itemID: "basic-001",
            level: .basic,
            firstSeenAt: firstSeenAt,
            lastReviewedAt: lastReviewedAt
        ))
        try context.save()

        let stored = try XCTUnwrap(context.fetch(FetchDescriptor<WordProgress>()).first)
        XCTAssertEqual(stored.firstSeenAt, firstSeenAt)
        XCTAssertEqual(stored.lastReviewedAt, lastReviewedAt)
    }

    func testSelectionPersistenceAndFetchedReviewIdentityDriveScheduling() throws {
        let context = try makeContext()
        let persistenceService = ProgressPersistenceService()
        let scheduler = ReviewScheduler(dayKeyService: dayKeyService())
        let items = [seedItem("basic-new", sortOrder: 1), seedItem("basic-review", sortOrder: 2)]
        context.insert(WordProgress(
            itemID: "basic-review",
            level: .basic,
            firstSeenAt: date("2026-07-01T02:00:00Z"),
            dueDayKey: "2026-07-10"
        ))
        try context.save()

        let progressRows = try context.fetch(FetchDescriptor<WordProgress>())
        let selection = DailySelectionService().selectItems(
            from: items,
            selectedLevel: .basic,
            contentLanguageCode: "en",
            supportLanguageCode: "zh-Hant",
            firstSeenItemIDs: Set(progressRows.compactMap { $0.firstSeenAt == nil ? nil : $0.itemID }),
            dueReviewItemIDs: scheduler.allDueItems(from: progressRows, on: "2026-07-10").map(\.itemID),
            targetCount: 2
        )
        _ = try persistenceService.session(
            for: "2026-07-10",
            itemIDs: selection.itemIDs,
            reviewItemIDs: Set(selection.reviewItemIDs),
            in: context
        )
        _ = try persistenceService.wordProgress(for: "basic-new", level: .basic, in: context)
        try context.save()

        let storedSession = try XCTUnwrap(context.fetch(FetchDescriptor<DailySession>()).first)
        let storedItems = storedSession.items.sorted { $0.position < $1.position }
        XCTAssertEqual(storedItems.map(\.isReviewFill), [false, true])

        let storedProgress = try context.fetch(FetchDescriptor<WordProgress>())
        let progressByID = Dictionary(uniqueKeysWithValues: storedProgress.map { ($0.itemID, $0) })
        let answeredAt = date("2026-07-10T02:00:00Z")
        for storedItem in storedItems {
            scheduler.applyAnswer(
                to: try XCTUnwrap(progressByID[storedItem.itemID]),
                wasCorrect: false,
                answeredAt: answeredAt,
                context: storedItem.reviewAnswerContext
            )
        }
        try context.save()

        let updatedProgress = try context.fetch(FetchDescriptor<WordProgress>())
        let dueDayByID = Dictionary(uniqueKeysWithValues: updatedProgress.map { ($0.itemID, $0.dueDayKey) })
        XCTAssertEqual(dueDayByID["basic-new"], "2026-07-10")
        XCTAssertEqual(dueDayByID["basic-review"], "2026-07-11")
    }

    func testQuizResultGuardKeepsFirstAnswerForSameDayAndItem() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        _ = try service.quizResult(
            dayKey: "2026-07-10",
            itemID: "basic-001",
            selectedOptionIndex: 1,
            correctOptionIndex: 1,
            in: context
        )
        _ = try service.quizResult(
            dayKey: "2026-07-10",
            itemID: "basic-001",
            selectedOptionIndex: 0,
            correctOptionIndex: 1,
            in: context
        )

        let results = try context.fetch(FetchDescriptor<QuizResult>())
        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results.first?.selectedOptionIndex, 1)
        XCTAssertEqual(results.first?.wasCorrect, true)
    }

    private func makeContext() throws -> ModelContext {
        let schema = Schema([
            WordProgress.self,
            DailySession.self,
            DailySessionItem.self,
            QuizResult.self
        ])
        let configuration = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)
        let container = try ModelContainer(for: schema, configurations: [configuration])
        return ModelContext(container)
    }

    private func seedItem(_ id: String, sortOrder: Int) -> VocabularySeedItem {
        let pronunciationID = "\(id)-pronunciation-1"
        let senseID = "\(id)-sense-1"
        return VocabularySeedItem(
            id: id,
            level: .basic,
            sortOrder: sortOrder,
            contentLanguageCode: "en",
            supportLanguageCodes: ["zh-Hant"],
            plainExpression: "plain \(id)",
            upgradedExpression: "upgraded \(id)",
            primarySenseID: senseID,
            pronunciations: [.init(id: pronunciationID, ipa: "tɛst", speechLocale: "en-US", region: "US")],
            senses: [.init(
                id: senseID,
                partOfSpeech: .phrase,
                meaning: ["en": "meaning", "zh-Hant": "meaning"],
                example: .init(text: "Example.", translation: ["zh-Hant": "例句。"]),
                pronunciationIDs: [pronunciationID]
            )],
            quiz: VocabularyQuiz(prompt: ["en": "prompt", "zh-Hant": "prompt"], options: ["A", "B"], correctOptionIndex: 0)
        )
    }

    private func dayKeyService() -> DayKeyService {
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Locale(identifier: "en_US_POSIX")
        calendar.timeZone = TimeZone(identifier: "Asia/Taipei")!
        return DayKeyService(calendar: calendar)
    }

    private func date(_ value: String) -> Date {
        ISO8601DateFormatter().date(from: value)!
    }
}
