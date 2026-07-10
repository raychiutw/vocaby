import XCTest
@testable import WordingDailyApp

final class QuizEngineTests: XCTestCase {
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
