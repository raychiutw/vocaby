import XCTest
@testable import WordingDailyApp

final class QuizEngineTests: XCTestCase {
    func testPracticeCenterPlanFiltersLevelAndSupportLanguageAndPrioritizesLearnedItems() {
        var items = makeItems(count: 8)
        items[5].level = .advanced
        items[6].supportLanguageCodes = ["ja"]
        items[7].level = .intermediate
        let learnedIDs = [items[0].id, items[1].id, items[5].id, items[6].id]
        let configuration = PracticeConfiguration(
            mode: .expressionChoice,
            questionCount: 3,
            timeLimitSeconds: 15,
            retriesWrongAnswers: true
        )
        var random = IncrementingRandomNumberGenerator()

        let plan = PracticeCenterPlan(
            seedItems: items,
            selectedLevel: .basic,
            supportLanguageCode: "zh-Hant",
            learnedItemIDs: learnedIDs,
            configuration: configuration,
            using: &random
        )

        XCTAssertEqual(Set(plan.questions.prefix(2).map(\.itemID)), Set(learnedIDs.prefix(2)))
        XCTAssertEqual(plan.questions.count, 3)
        XCTAssertTrue(plan.questions.allSatisfy { Set(items.prefix(5).map(\.id)).contains($0.itemID) })
        XCTAssertFalse(plan.questions.flatMap(\.options).contains(items[5].upgradedExpression))
        XCTAssertFalse(plan.questions.flatMap(\.options).contains(items[6].upgradedExpression))
    }

    func testPracticeCenterPlanUsesConfiguredModeCountAndFullLocalPoolForDistractors() throws {
        let items = makeItems(count: 6)
        let configuration = PracticeConfiguration(
            mode: .meaningChoice,
            questionCount: 1,
            timeLimitSeconds: 30,
            retriesWrongAnswers: false
        )
        var random = IncrementingRandomNumberGenerator()

        let plan = PracticeCenterPlan(
            seedItems: items,
            selectedLevel: .basic,
            supportLanguageCode: "zh-Hant",
            learnedItemIDs: [],
            configuration: configuration,
            using: &random
        )
        let question = try XCTUnwrap(plan.questions.first)

        XCTAssertEqual(plan.configuration, configuration)
        XCTAssertEqual(plan.questions.count, 1)
        XCTAssertEqual(question.mode, .meaningChoice)
        XCTAssertEqual(question.options.count, 4)
    }

    func testPracticeCenterPlanCreatesFreshRunIdentity() {
        let items = makeItems(count: 1)
        var firstRandom = IncrementingRandomNumberGenerator()
        var secondRandom = IncrementingRandomNumberGenerator()

        let first = PracticeCenterPlan(
            seedItems: items,
            selectedLevel: .basic,
            supportLanguageCode: "zh-Hant",
            learnedItemIDs: [],
            configuration: .daily,
            using: &firstRandom
        )
        let second = PracticeCenterPlan(
            seedItems: items,
            selectedLevel: .basic,
            supportLanguageCode: "zh-Hant",
            learnedItemIDs: [],
            configuration: .daily,
            using: &secondRandom
        )

        XCTAssertNotEqual(first.runID, second.runID)
    }

    func testPracticeCenterOptionsAndDefaultsMatchSetup() {
        XCTAssertEqual(PracticeConfiguration.questionCounts, [5, 10, 15, 20])
        XCTAssertEqual(PracticeConfiguration.timeLimits, [10, 15, 20, 30])
        XCTAssertEqual(
            PracticeCenterPlan.defaultConfiguration,
            PracticeConfiguration(
                mode: .mixed,
                questionCount: 10,
                timeLimitSeconds: 15,
                retriesWrongAnswers: true
            )
        )
    }

    func testPracticeSelectionUsesLearnedItemsThenFillsFromLocalSeed() {
        let items = makeItems(count: 6)
        var random = IncrementingRandomNumberGenerator()

        let selected = QuizEngine().selectPracticeItems(
            from: items,
            learnedItemIDs: [items[0].id, items[1].id],
            count: 5,
            using: &random
        )

        XCTAssertEqual(selected.count, 5)
        XCTAssertTrue(Set([items[0].id, items[1].id]).isSubset(of: Set(selected.map(\.id))))
        XCTAssertEqual(Set(selected.map(\.id)).count, 5)
    }

    func testExpressionChoiceUsesPlainPromptAndLocalUpgrades() throws {
        let items = makeItems(count: 5)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .expressionChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, items[0].plainExpression)
        XCTAssertEqual(question.correctAnswer, items[0].upgradedExpression)
        XCTAssertEqual(question.options.count, 4)
        XCTAssertEqual(Set(question.options).count, 4)
    }

    func testDistractorsStayInLevelAndDeduplicateVisibleText() throws {
        var items = makeItems(count: 6)
        items[4].level = .advanced
        items[5].upgradedExpression = items[1].upgradedExpression
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .expressionChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertFalse(question.options.contains(items[4].upgradedExpression))
        XCTAssertEqual(Set(question.options).count, question.options.count)
        XCTAssertEqual(question.options.filter { $0 == items[1].upgradedExpression }.count, 1)
    }

    func testMeaningChoiceUsesUpgradePromptAndLocalizedMeanings() throws {
        let items = makeItems(count: 5)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .meaningChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, items[0].upgradedExpression)
        XCTAssertEqual(question.correctAnswer, items[0].meaning["zh-Hant"])
        XCTAssertEqual(Set(question.options).count, 4)
    }

    func testListeningChoiceCarriesSpeechTextWithoutShowingAnswer() throws {
        let items = makeItems(count: 5)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .listeningChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, "")
        XCTAssertEqual(question.spokenText, items[0].pronunciationText)
        XCTAssertEqual(question.correctAnswer, items[0].upgradedExpression)
    }

    func testSpellingUsesMeaningAndIgnoresCaseAndEdgeWhitespace() throws {
        let items = makeItems(count: 1)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: items, candidates: items, mode: .spelling,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, items[0].meaning["zh-Hant"])
        XCTAssertTrue(QuizEngine().isCorrect("  \(items[0].upgradedExpression.uppercased())  ", for: question))
        XCTAssertFalse(QuizEngine().isCorrect("different answer", for: question))
    }

    func testMixedUsesShuffledFourModeBags() {
        let items = makeItems(count: 12)
        var random = IncrementingRandomNumberGenerator()
        let questions = QuizEngine().makeQuestions(
            for: items, candidates: items, mode: .mixed,
            supportLanguageCode: "zh-Hant", using: &random
        )
        let concreteModes = PracticeMode.allCases.filter { $0 != .mixed }

        XCTAssertEqual(Set(questions.prefix(4).map(\.mode)), Set(concreteModes))
        XCTAssertEqual(Set(questions.dropFirst(4).prefix(4).map(\.mode)), Set(concreteModes))
        XCTAssertNotEqual(questions.prefix(4).map(\.mode), concreteModes)
        XCTAssertFalse(questions.contains { $0.mode == .mixed })
    }

    func testMixedShufflesCorrectPositions() {
        let items = makeItems(count: 12)
        var random = IncrementingRandomNumberGenerator()
        let questions = QuizEngine().makeQuestions(
            for: items, candidates: items, mode: .mixed,
            supportLanguageCode: "zh-Hant", using: &random
        )

        XCTAssertGreaterThan(Set(questions.compactMap(\.correctOptionIndex)).count, 1)
    }

    func testDailyPracticePlanLearnsNewItemsAndQuizzesAllUnansweredInSessionOrder() {
        let items = makeItems(count: 3)
        let answeredAt = Date(timeIntervalSince1970: 100)
        let session = DailySession(dayKey: "2026-07-10", targetItemCount: 3)
        session.items = [
            DailySessionItem(itemID: items[2].id, position: 2, answeredAt: answeredAt),
            DailySessionItem(itemID: items[1].id, position: 1, isReviewFill: true),
            DailySessionItem(itemID: items[0].id, position: 0)
        ]

        let plan = DailyPracticePlan(
            session: session,
            seedItems: items,
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(plan.learnItems.map(\.id), [items[0].id])
        XCTAssertEqual(plan.quizQuestions.map(\.itemID), [items[0].id, items[1].id])
        XCTAssertEqual(plan.runID, session.dayKey)

        session.items.first { $0.itemID == items[0].id }?.answeredAt = answeredAt
        let resumedPlan = DailyPracticePlan(
            session: session,
            seedItems: items,
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(resumedPlan.quizQuestions.map(\.itemID), [items[1].id])
        XCTAssertEqual(resumedPlan.runID, plan.runID)
    }

    func testDailyPracticePlanFailsClosedWhenUnansweredItemIsMissingFromSeed() {
        let items = makeItems(count: 1)
        let session = DailySession(dayKey: "2026-07-10", targetItemCount: 2)
        session.items = [
            DailySessionItem(itemID: items[0].id, position: 0),
            DailySessionItem(itemID: "missing-seed", position: 1, isReviewFill: true)
        ]

        let plan = DailyPracticePlan(
            session: session,
            seedItems: items,
            supportLanguageCode: "zh-Hant"
        )

        XCTAssertEqual(plan.missingSeedItemIDs, ["missing-seed"])
        XCTAssertTrue(plan.learnItems.isEmpty)
        XCTAssertTrue(plan.quizQuestions.isEmpty)
    }

    func testReviewPracticePlanPreservesDueOrderAndUsesFullSeedForMixedQuestions() {
        let seedItems = makeItems(count: 6)
        let dueItems = [seedItems[2], seedItems[0]]
        var random = IncrementingRandomNumberGenerator()

        let plan = ReviewPracticePlan(
            dayKey: "2026-07-10",
            items: dueItems,
            seedItems: seedItems,
            supportLanguageCode: "zh-Hant",
            using: &random
        )

        XCTAssertEqual(plan.quizQuestions.map(\.itemID), dueItems.map(\.id))
        XCTAssertTrue(plan.quizQuestions.allSatisfy { $0.mode != .mixed })
        XCTAssertEqual(plan.quizQuestions.first?.options.count, 4)

        var repeatedRandom = IncrementingRandomNumberGenerator()
        let repeatedPlan = ReviewPracticePlan(
            dayKey: "2026-07-10",
            items: dueItems,
            seedItems: seedItems,
            supportLanguageCode: "zh-Hant",
            using: &repeatedRandom
        )
        XCTAssertEqual(repeatedPlan.runID, plan.runID)

        var reorderedRandom = IncrementingRandomNumberGenerator()
        let reorderedPlan = ReviewPracticePlan(
            dayKey: "2026-07-10",
            items: Array(dueItems.reversed()),
            seedItems: seedItems,
            supportLanguageCode: "zh-Hant",
            using: &reorderedRandom
        )
        XCTAssertNotEqual(reorderedPlan.runID, plan.runID)
    }

    func testQuestionGenerationUsesFewerUniqueOptionsWhenSeedIsExhausted() throws {
        let items = makeItems(count: 2)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .expressionChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.options.count, 2)
        XCTAssertEqual(Set(question.options).count, 2)
        XCTAssertTrue(question.options.contains(question.correctAnswer))
    }

    func testSubmitFreezesFeedbackOnTheCurrentQuestion() throws {
        let first = makeQuestion("first")
        let second = makeQuestion("second")
        var state = QuizRunState(questions: [first, second])

        let initialFeedback = try XCTUnwrap(state.submit("wrong first"))
        let repeatedFeedback = state.submit(first.correctAnswer)

        XCTAssertEqual(state.currentQuestion, first)
        XCTAssertEqual(state.currentFeedback, initialFeedback)
        XCTAssertNil(repeatedFeedback)
        XCTAssertEqual(state.firstAttempts, [initialFeedback])
    }

    func testTimeoutAfterSubmissionDoesNotReturnAnotherAttempt() throws {
        let question = makeQuestion("first")
        var state = QuizRunState(questions: [question])

        let initialFeedback = try XCTUnwrap(state.submit(question.correctAnswer))

        XCTAssertNil(state.timeout())
        XCTAssertEqual(state.currentFeedback, initialFeedback)
        XCTAssertEqual(state.firstAttempts, [initialFeedback])
    }

    func testAdvanceIsTheOnlyTransitionToTheNextQuestion() {
        let first = makeQuestion("first")
        let second = makeQuestion("second")
        var state = QuizRunState(questions: [first, second])

        state.advance()
        XCTAssertEqual(state.currentQuestion, first)

        state.submit(first.correctAnswer)
        XCTAssertEqual(state.currentQuestion, first)

        state.advance()
        XCTAssertEqual(state.currentQuestion, second)
        XCTAssertNil(state.currentFeedback)
    }

    func testTimeoutRecordsWrongAttemptAndWaitsForAdvance() throws {
        let first = makeQuestion("first")
        let second = makeQuestion("second")
        var state = QuizRunState(questions: [first, second])

        let attempt = try XCTUnwrap(state.timeout())

        XCTAssertFalse(attempt.wasCorrect)
        XCTAssertTrue(attempt.timedOut)
        XCTAssertTrue(attempt.isFirstAttempt)
        XCTAssertEqual(state.currentQuestion, first)
        XCTAssertEqual(state.currentFeedback, attempt)

        state.advance()
        XCTAssertEqual(state.currentQuestion, second)
    }

    func testRetryContainsOnlyWrongQuestionsAndMarksAttemptsAsRetries() throws {
        let wrongQuestion = makeQuestion("wrong", mode: .listeningChoice)
        let correctQuestion = makeQuestion("correct", mode: .spelling)
        var state = QuizRunState(questions: [wrongQuestion, correctQuestion])

        state.submit("wrong answer")
        state.advance()
        state.submit(correctQuestion.correctAnswer)
        state.advance()

        XCTAssertTrue(state.startRetry())
        XCTAssertEqual(state.questions, [wrongQuestion])
        XCTAssertEqual(state.currentQuestion?.mode, .listeningChoice)
        XCTAssertTrue(state.isRetryRound)

        let retryAttempt = try XCTUnwrap(state.submit(wrongQuestion.correctAnswer))
        XCTAssertFalse(retryAttempt.isFirstAttempt)
        XCTAssertEqual(state.retryAttempts, [retryAttempt])
        XCTAssertEqual(state.firstAttempts.count, 2)
    }

    func testResetStartsNewRunWithClearedHistory() {
        let original = makeQuestion("original")
        let replacement = makeQuestion("replacement", mode: .spelling)
        var state = QuizRunState(questions: [original])

        state.submit("wrong")
        state.advance()
        XCTAssertTrue(state.startRetry())
        state.submit("still wrong")
        state.advance()

        state.reset(with: [replacement])

        XCTAssertEqual(state.questions, [replacement])
        XCTAssertEqual(state.currentQuestion, replacement)
        XCTAssertEqual(state.currentIndex, 0)
        XCTAssertNil(state.currentFeedback)
        XCTAssertTrue(state.firstAttempts.isEmpty)
        XCTAssertTrue(state.retryAttempts.isEmpty)
        XCTAssertFalse(state.isRetryRound)
    }

    func testOptionPersistenceIndicesUseVisibleOptionPositions() {
        let question = QuizQuestion(
            id: "choice-expressionChoice",
            itemID: "choice",
            mode: .expressionChoice,
            prompt: "prompt",
            options: ["option A", "correct", "option C", "selected"],
            correctAnswer: "correct",
            spokenText: nil
        )

        XCTAssertEqual(
            question.persistenceIndices(for: "selected", wasCorrect: false),
            QuizPersistenceIndices(selected: 3, correct: 1)
        )
    }

    func testSpellingPersistenceIndicesUseSyntheticBinaryValues() {
        let question = makeQuestion("spelling", mode: .spelling)

        XCTAssertEqual(
            question.persistenceIndices(for: question.correctAnswer, wasCorrect: true),
            QuizPersistenceIndices(selected: 1, correct: 1)
        )
        XCTAssertEqual(
            question.persistenceIndices(for: "wrong", wasCorrect: false),
            QuizPersistenceIndices(selected: 0, correct: 1)
        )
    }

    private func makeQuestion(_ id: String, mode: PracticeMode = .expressionChoice) -> QuizQuestion {
        let correctAnswer = "correct \(id)"
        return QuizQuestion(
            id: "\(id)-\(mode.rawValue)",
            itemID: id,
            mode: mode,
            prompt: "prompt \(id)",
            options: mode == .spelling ? [] : ["wrong \(id)", correctAnswer],
            correctAnswer: correctAnswer,
            spokenText: mode == .listeningChoice ? correctAnswer : nil
        )
    }

    private func makeItems(count: Int) -> [VocabularySeedItem] {
        (1...count).map { index in
            VocabularySeedItem(
                id: "basic-\(index)", level: .basic, sortOrder: index,
                contentLanguageCode: "en", supportLanguageCodes: ["zh-Hant"],
                plainExpression: "plain \(index)", upgradedExpression: "upgrade \(index)",
                meaning: ["en": "definition \(index)", "zh-Hant": "意思 \(index)"],
                example: .init(text: "Example \(index).", translation: ["zh-Hant": "例句 \(index)。"]),
                pronunciationText: "upgrade \(index)",
                quiz: .init(prompt: ["zh-Hant": "legacy"], options: ["legacy A", "legacy B"], correctOptionIndex: 0)
            )
        }
    }
}

private struct IncrementingRandomNumberGenerator: RandomNumberGenerator {
    private var value: UInt64 = 0

    mutating func next() -> UInt64 {
        defer { value &+= 1 }
        return value
    }
}
