import SwiftData
import XCTest
@testable import Vocaby

final class AnswerRecorderTests: XCTestCase {
    private let answeredAt = Date(timeIntervalSince1970: 1_800_000_000)
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

    /// 另開一個 context 讀資料:只有真正 save 過的內容才看得到。
    private func persisted<T: PersistentModel>(_ type: T.Type) throws -> [T] {
        try ModelContext(container).fetch(FetchDescriptor<T>())
    }

    private func answer(
        _ itemID: String = "basic-001",
        correct: Bool = true,
        first: Bool = true
    ) -> RecordedAnswer {
        RecordedAnswer(
            itemID: itemID, level: .basic, mode: .meaningChoice,
            wasCorrect: correct, isFirstAttempt: first,
            selectedOptionIndex: correct ? 2 : 0, correctOptionIndex: 2
        )
    }

    func testFreePracticeCreatesProgressAndAttemptButNoQuizResult() throws {
        let context = ModelContext(container)

        try AnswerRecorder().record(answer(), from: .freePractice(runID: "run-1"), at: answeredAt, in: context)

        let progress = try XCTUnwrap(persisted(WordProgress.self).first)
        XCTAssertEqual(progress.itemID, "basic-001")
        XCTAssertNotNil(progress.dueDayKey, "答案應已套用到排程")
        XCTAssertEqual(try persisted(PracticeAttemptRecord.self).map(\.runID), ["run-1"])
        XCTAssertTrue(try persisted(QuizResult.self).isEmpty)
    }

    func testReviewRecordsAQuizResultUnderTheGivenDayKey() throws {
        let context = ModelContext(container)
        context.insert(WordProgress(itemID: "basic-001", level: .basic, firstSeenAt: answeredAt, dueDayKey: "2026-07-09"))
        try context.save()

        try AnswerRecorder().record(
            answer(correct: false),
            from: .review(runID: "run-1", resultDayKey: "2026-07-10"),
            at: answeredAt,
            in: context
        )

        let result = try XCTUnwrap(persisted(QuizResult.self).first)
        XCTAssertEqual(result.id, "2026-07-10#basic-001")
        XCTAssertEqual(result.selectedOptionIndex, 0)
        XCTAssertEqual(result.correctOptionIndex, 2)
        XCTAssertEqual(try persisted(PracticeAttemptRecord.self).map(\.runID), ["run-1"])
    }

    func testReviewRequiresExistingProgressAndLeavesNothingBehindWhenMissing() throws {
        let context = ModelContext(container)

        XCTAssertThrowsError(
            try AnswerRecorder().record(
                answer(), from: .review(runID: "2026-07-10", resultDayKey: "2026-07-10"),
                at: answeredAt, in: context
            )
        )

        XCTAssertTrue(try persisted(WordProgress.self).isEmpty)
        XCTAssertTrue(try persisted(PracticeAttemptRecord.self).isEmpty)
        XCTAssertTrue(try persisted(QuizResult.self).isEmpty)
    }

    func testReviewUpdatesTheExistingProgressRow() throws {
        let context = ModelContext(container)
        context.insert(WordProgress(itemID: "basic-001", level: .basic, firstSeenAt: answeredAt, dueDayKey: "2026-07-09"))
        try context.save()

        try AnswerRecorder().record(
            answer(correct: false),
            from: .review(runID: "2026-07-10", resultDayKey: "2026-07-10"),
            at: answeredAt,
            in: context
        )

        let rows = try persisted(WordProgress.self)
        XCTAssertEqual(rows.count, 1)
        XCTAssertEqual(rows.first?.wrongCount, 1)
        XCTAssertEqual(try persisted(QuizResult.self).count, 1)
    }

    func testRetryAttemptOnlyRecordsTheAttempt() throws {
        let context = ModelContext(container)

        try AnswerRecorder().record(
            answer(first: false),
            from: .freePractice(runID: "run-1"),
            at: answeredAt,
            in: context
        )

        XCTAssertTrue(try persisted(WordProgress.self).isEmpty)
        XCTAssertTrue(try persisted(QuizResult.self).isEmpty)
        XCTAssertEqual(try persisted(PracticeAttemptRecord.self).count, 1)
    }

    func testRecordingTheSameReviewAnswerTwiceKeepsOneQuizResult() throws {
        let context = ModelContext(container)
        context.insert(WordProgress(itemID: "basic-001", level: .basic, firstSeenAt: answeredAt, dueDayKey: "2026-07-09"))
        try context.save()
        let source = AnswerSource.review(runID: "run-1", resultDayKey: "2026-07-10")

        try AnswerRecorder().record(answer(), from: source, at: answeredAt, in: context)
        try AnswerRecorder().record(answer(), from: source, at: answeredAt, in: context)

        XCTAssertEqual(try persisted(QuizResult.self).count, 1)
        XCTAssertEqual(try persisted(PracticeAttemptRecord.self).count, 2)
    }

    func testEarlierUnsavedChangesInTheContextAreRolledBackOnFailure() throws {
        let context = ModelContext(container)
        // 呼叫端(例如每日練習)在 record 之前先改了 session item;失敗時要一起回滾
        context.insert(PracticeAttemptRecord(runID: "stray", itemID: "x", level: .basic, mode: .meaningChoice, wasCorrect: true))

        XCTAssertThrowsError(
            try AnswerRecorder().record(
                answer(), from: .review(runID: "r", resultDayKey: "d"), at: answeredAt, in: context
            )
        )

        XCTAssertTrue(try persisted(PracticeAttemptRecord.self).isEmpty)
        XCTAssertFalse(context.hasChanges)
    }

    func testEveryRecordCarriesTheGivenAnswerTimeInsteadOfTheSystemClock() throws {
        let context = ModelContext(container)
        context.insert(WordProgress(itemID: "basic-001", level: .basic, firstSeenAt: answeredAt.addingTimeInterval(-60), dueDayKey: "2026-07-09"))
        try context.save()

        try AnswerRecorder().record(
            answer(),
            from: .review(runID: "run-1", resultDayKey: "2026-07-10"),
            at: answeredAt,
            in: context
        )

        XCTAssertEqual(try persisted(PracticeAttemptRecord.self).map(\.answeredAt), [answeredAt])
        XCTAssertEqual(try persisted(QuizResult.self).map(\.answeredAt), [answeredAt])
        XCTAssertEqual(try persisted(WordProgress.self).first?.lastReviewedAt, answeredAt)
    }

    func testCallerEditsToExistingModelsAreRolledBackOnFailure() throws {
        let context = ModelContext(container)
        let session = DailySession(dayKey: "2026-07-10")
        context.insert(session)
        try context.save()

        // 呼叫端(每日練習)在 record 之前先改了既有 model;record 失敗時要連這些一起回滾
        session.completedAt = answeredAt
        XCTAssertThrowsError(
            try AnswerRecorder().record(
                answer(), from: .review(runID: "r", resultDayKey: "d"), at: answeredAt, in: context
            )
        )

        XCTAssertNil(try persisted(DailySession.self).first?.completedAt)
        XCTAssertNil(session.completedAt)
    }
}
