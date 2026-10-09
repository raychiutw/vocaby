import SwiftData
import XCTest
@testable import Vocaby

final class DailySessionServiceTests: XCTestCase {
    private let dayKey = "2026-07-10"
    private let now = DayKeyService().date(for: "2026-07-10")!.addingTimeInterval(3600)
    private var container: ModelContainer!

    override func setUpWithError() throws {
        let schema = Schema([
            WordProgress.self, DailySession.self, DailySessionItem.self,
            QuizResult.self, PracticeAttemptRecord.self
        ])
        container = try ModelContainer(
            for: schema,
            configurations: [ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)]
        )
    }

    private func persisted<T: PersistentModel>(_ type: T.Type) throws -> [T] {
        try ModelContext(container).fetch(FetchDescriptor<T>())
    }

    private func sessionForToday(_ context: ModelContext, seed: [VocabularySeedItem]) throws -> DailySession? {
        try DailySessionService().sessionForToday(
            dayKey: dayKey,
            seed: seed,
            progressRows: try context.fetch(FetchDescriptor<WordProgress>()),
            preferences: .defaults,
            now: now,
            in: context
        )
    }

    func testCreatesItemsInPlanOrderWithReviewFlags() throws {
        let context = ModelContext(container)
        // 4 個字、目標 10:新字 002–004,不足的補到期複習 001
        context.insert(WordProgress(itemID: "basic-001", level: .basic, firstSeenAt: now, dueDayKey: dayKey))
        try context.save()

        let session = try XCTUnwrap(sessionForToday(context, seed: seeds(4)))

        let items = session.items.sorted { $0.position < $1.position }
        XCTAssertEqual(items.map(\.itemID), ["basic-002", "basic-003", "basic-004", "basic-001"])
        XCTAssertEqual(items.map(\.isReviewFill), [false, false, false, true])
        XCTAssertEqual(items.map(\.position), [0, 1, 2, 3])
        XCTAssertEqual(session.targetItemCount, 4)
        XCTAssertEqual(session.createdAt, now, "建立時間用傳入的 now,不是系統時間")
    }

    func testCreatingASessionDoesNotMarkItemsAsSeen() throws {
        let context = ModelContext(container)

        _ = try sessionForToday(context, seed: seeds(4))

        XCTAssertTrue(try persisted(WordProgress.self).isEmpty, "firstSeenAt 在答題時才由 ReviewScheduler 設定")
    }

    func testAnExistingSessionIsReusedAndItsItemsAreNotReplaced() throws {
        let context = ModelContext(container)
        _ = try sessionForToday(context, seed: seeds(4))

        let second = try XCTUnwrap(sessionForToday(context, seed: seeds(8)))

        XCTAssertEqual(second.items.count, 4)
        XCTAssertEqual(try persisted(DailySession.self).count, 1)
    }

    func testNothingToStudyReturnsNilAndDoesNotPersistAnEmptySession() throws {
        let context = ModelContext(container)

        XCTAssertNil(try sessionForToday(context, seed: []))
        XCTAssertTrue(try persisted(DailySession.self).isEmpty)
    }

    func testAnEmptyExistingSessionIsFilledInsteadOfDuplicated() throws {
        let context = ModelContext(container)
        context.insert(DailySession(dayKey: dayKey, targetItemCount: 0, createdAt: now))
        try context.save()

        let session = try XCTUnwrap(sessionForToday(context, seed: seeds(4)))

        XCTAssertEqual(session.items.count, 4)
        XCTAssertEqual(try persisted(DailySession.self).count, 1)
    }

    func testTheSessionAndItsItemsArePersistedInOneSave() throws {
        let context = ModelContext(container)

        _ = try sessionForToday(context, seed: seeds(4))

        // 用另一個 context 讀:只有真正 save 過的才看得到
        XCTAssertEqual(try persisted(DailySession.self).first?.items.count, 4)
        XCTAssertFalse(context.hasChanges)
    }

    func testAppendsTheNextUnseenItemsAndReopensTheSession() throws {
        let context = ModelContext(container)
        let seed = seeds(25)
        let session = DailySession(dayKey: dayKey, targetItemCount: 10, createdAt: now, completedAt: now)
        for position in 0..<10 {
            session.items.append(DailySessionItem(
                itemID: String(format: "basic-%03d", position + 1), position: position, answeredAt: now, wasCorrect: true
            ))
            context.insert(WordProgress(itemID: String(format: "basic-%03d", position + 1), level: .basic, firstSeenAt: now))
        }
        context.insert(session)
        try context.save()

        let added = try DailySessionService().appendExtraItems(
            to: session, seed: seed,
            progressRows: try context.fetch(FetchDescriptor<WordProgress>()),
            level: .basic, in: context
        )

        XCTAssertTrue(added)
        let items = session.items.sorted { $0.position < $1.position }
        XCTAssertEqual(items.count, 20)
        XCTAssertEqual(items.suffix(10).map(\.itemID), (11...20).map { String(format: "basic-%03d", $0) })
        XCTAssertEqual(items.suffix(10).map(\.position), Array(10..<20))
        XCTAssertEqual(session.targetItemCount, 20)
        XCTAssertNil(session.completedAt)
        XCTAssertEqual(try persisted(DailySession.self).first?.items.count, 20)
    }

    func testAppendingDoesNothingWhenNoUnseenItemsRemain() throws {
        let context = ModelContext(container)
        let session = DailySession(dayKey: dayKey, targetItemCount: 2, createdAt: now, completedAt: now)
        session.items = [
            DailySessionItem(itemID: "basic-001", position: 0, answeredAt: now, wasCorrect: true),
            DailySessionItem(itemID: "basic-002", position: 1, answeredAt: now, wasCorrect: true)
        ]
        context.insert(session)
        try context.save()

        let added = try DailySessionService().appendExtraItems(
            to: session, seed: seeds(2), progressRows: [], level: .basic, in: context
        )

        XCTAssertFalse(added)
        XCTAssertEqual(session.items.count, 2)
        XCTAssertEqual(session.completedAt, now)
    }

    private func seeds(_ count: Int) -> [VocabularySeedItem] {
        (1...count).map { index in
            let id = String(format: "basic-%03d", index)
            let pronunciationID = "\(id)-pronunciation-1"
            let senseID = "\(id)-sense-1"
            return VocabularySeedItem(
                id: id, level: .basic, sortOrder: index,
                contentLanguageCode: "en", supportLanguageCodes: ["zh-Hant"],
                plainExpression: "plain \(id)", upgradedExpression: "upgraded \(id)",
                primarySenseID: senseID,
                pronunciations: [.init(id: pronunciationID, ipa: "tɛst", speechLocale: "en-US", region: "US")],
                senses: [.init(
                    id: senseID, partOfSpeech: .phrase,
                    meaning: ["en": "meaning", "zh-Hant": "meaning"],
                    example: .init(text: "Example.", translation: ["zh-Hant": "例句。"]),
                    pronunciationIDs: [pronunciationID]
                )],
                quiz: VocabularyQuiz(prompt: ["en": "prompt", "zh-Hant": "prompt"], options: ["A", "B"], correctOptionIndex: 0)
            )
        }
    }
}
