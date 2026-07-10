import SwiftData
import XCTest
@testable import WordingDailyApp

final class PersistenceGuardTests: XCTestCase {
    func testSessionGuardReusesExistingDayKey() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        _ = try service.session(for: "2026-07-10", targetItemCount: 10, in: context)
        _ = try service.session(for: "2026-07-10", targetItemCount: 10, in: context)

        let sessions = try context.fetch(FetchDescriptor<DailySession>())
        XCTAssertEqual(sessions.count, 1)
        XCTAssertEqual(sessions.first?.dayKey, "2026-07-10")
    }

    func testSessionItemsAreCreatedInSelectionOrder() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        let session = try service.session(
            for: "2026-07-10",
            itemIDs: ["basic-001", "basic-002", "basic-003"],
            targetItemCount: 10,
            in: context
        )

        let items = session.items.sorted { $0.position < $1.position }
        XCTAssertEqual(items.map(\.itemID), ["basic-001", "basic-002", "basic-003"])
        XCTAssertEqual(items.map(\.position), [0, 1, 2])
    }

    func testSessionItemsAreNotReplacedForExistingSession() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        _ = try service.session(
            for: "2026-07-10",
            itemIDs: ["basic-001", "basic-002"],
            targetItemCount: 10,
            in: context
        )
        let existing = try service.session(
            for: "2026-07-10",
            itemIDs: ["basic-003", "basic-004"],
            targetItemCount: 10,
            in: context
        )

        let items = existing.items.sorted { $0.position < $1.position }
        XCTAssertEqual(items.map(\.itemID), ["basic-001", "basic-002"])
    }

    func testWordProgressGuardReusesExistingItemID() throws {
        let context = try makeContext()
        let service = ProgressPersistenceService()

        _ = try service.wordProgress(for: "basic-001", level: .basic, in: context)
        _ = try service.wordProgress(for: "basic-001", level: .basic, in: context)

        let progressRows = try context.fetch(FetchDescriptor<WordProgress>())
        XCTAssertEqual(progressRows.count, 1)
        XCTAssertEqual(progressRows.first?.itemID, "basic-001")
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
}
