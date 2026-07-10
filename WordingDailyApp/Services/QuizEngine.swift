import Foundation

enum PracticeMode: String, CaseIterable, Codable, Identifiable {
    case mixed
    case expressionChoice
    case meaningChoice
    case listeningChoice
    case spelling

    var id: String { rawValue }
}

struct PracticeConfiguration: Equatable {
    static let questionCounts = [5, 10, 15, 20]
    static let timeLimits = [10, 15, 20, 30]
    static let daily = PracticeConfiguration(
        mode: .mixed,
        questionCount: 10,
        timeLimitSeconds: 15,
        retriesWrongAnswers: true
    )

    var mode: PracticeMode
    var questionCount: Int
    var timeLimitSeconds: Int
    var retriesWrongAnswers: Bool
}

struct QuizQuestion: Identifiable, Equatable {
    let id: String
    let itemID: String
    let mode: PracticeMode
    let prompt: String
    let options: [String]
    let correctAnswer: String
    let spokenText: String?

    var correctOptionIndex: Int? { options.firstIndex(of: correctAnswer) }
}

struct QuizPersistenceIndices: Equatable {
    let selected: Int
    let correct: Int
}

extension QuizQuestion {
    func persistenceIndices(for submittedAnswer: String, wasCorrect: Bool) -> QuizPersistenceIndices {
        if mode == .spelling {
            return QuizPersistenceIndices(selected: wasCorrect ? 1 : 0, correct: 1)
        }

        return QuizPersistenceIndices(
            selected: options.firstIndex(of: submittedAnswer) ?? -1,
            correct: correctOptionIndex ?? -1
        )
    }
}

struct QuizAttempt: Equatable {
    let question: QuizQuestion
    let submittedAnswer: String
    let wasCorrect: Bool
    let timedOut: Bool
    let isFirstAttempt: Bool
}

struct QuizRunState {
    private(set) var questions: [QuizQuestion]
    private(set) var currentIndex = 0
    private(set) var currentFeedback: QuizAttempt?
    private(set) var firstAttempts: [QuizAttempt] = []
    private(set) var retryAttempts: [QuizAttempt] = []
    private(set) var isRetryRound = false

    var currentQuestion: QuizQuestion? {
        questions.indices.contains(currentIndex) ? questions[currentIndex] : nil
    }

    init(questions: [QuizQuestion]) {
        self.questions = questions
    }

    @discardableResult
    mutating func submit(_ submittedAnswer: String) -> QuizAttempt? {
        record(submittedAnswer: submittedAnswer, timedOut: false)
    }

    @discardableResult
    mutating func timeout() -> QuizAttempt? {
        record(submittedAnswer: "", timedOut: true)
    }

    mutating func advance() {
        guard currentFeedback != nil else { return }

        currentIndex += 1
        currentFeedback = nil
    }

    @discardableResult
    mutating func startRetry() -> Bool {
        guard currentQuestion == nil else { return false }

        let attempts = isRetryRound ? retryAttempts : firstAttempts
        let wrongQuestions = attempts.filter { !$0.wasCorrect }.map(\.question)
        guard !wrongQuestions.isEmpty else { return false }

        questions = wrongQuestions
        currentIndex = 0
        currentFeedback = nil
        retryAttempts = []
        isRetryRound = true
        return true
    }

    private mutating func record(submittedAnswer: String, timedOut: Bool) -> QuizAttempt? {
        if let currentFeedback {
            return currentFeedback
        }
        guard let currentQuestion else { return nil }

        let attempt = QuizAttempt(
            question: currentQuestion,
            submittedAnswer: submittedAnswer,
            wasCorrect: !timedOut && QuizEngine().isCorrect(submittedAnswer, for: currentQuestion),
            timedOut: timedOut,
            isFirstAttempt: !isRetryRound
        )
        currentFeedback = attempt

        if isRetryRound {
            retryAttempts.append(attempt)
        } else {
            firstAttempts.append(attempt)
        }

        return attempt
    }
}

struct QuizEngine {
    func selectPracticeItems(
        from items: [VocabularySeedItem],
        learnedItemIDs: [String],
        count: Int
    ) -> [VocabularySeedItem] {
        var random = SystemRandomNumberGenerator()
        return selectPracticeItems(
            from: items,
            learnedItemIDs: learnedItemIDs,
            count: count,
            using: &random
        )
    }

    func selectPracticeItems<Random: RandomNumberGenerator>(
        from items: [VocabularySeedItem],
        learnedItemIDs: [String],
        count: Int,
        using random: inout Random
    ) -> [VocabularySeedItem] {
        guard count > 0 else { return [] }

        let learnedIDs = Set(learnedItemIDs)
        let learned = shuffled(items.filter { learnedIDs.contains($0.id) }, using: &random)
        let unseen = shuffled(items.filter { !learnedIDs.contains($0.id) }, using: &random)

        return Array((learned + unseen).prefix(count))
    }

    func makeQuestions(
        for items: [VocabularySeedItem],
        candidates: [VocabularySeedItem],
        mode: PracticeMode,
        supportLanguageCode: String
    ) -> [QuizQuestion] {
        var random = SystemRandomNumberGenerator()
        return makeQuestions(
            for: items,
            candidates: candidates,
            mode: mode,
            supportLanguageCode: supportLanguageCode,
            using: &random
        )
    }

    func makeQuestions<Random: RandomNumberGenerator>(
        for items: [VocabularySeedItem],
        candidates: [VocabularySeedItem],
        mode: PracticeMode,
        supportLanguageCode: String,
        using random: inout Random
    ) -> [QuizQuestion] {
        let concreteModes = PracticeMode.allCases.filter { $0 != .mixed }
        var mixedModes: [PracticeMode] = []
        if mode == .mixed {
            while mixedModes.count < items.count {
                mixedModes.append(contentsOf: shuffled(concreteModes, using: &random))
            }
        }

        return items.enumerated().map { index, item in
            let questionMode = mode == .mixed ? mixedModes[index] : mode
            let correctAnswer = answer(
                for: item,
                mode: questionMode,
                supportLanguageCode: supportLanguageCode
            )
            let options = questionMode == .spelling ? [] : makeOptions(
                correctAnswer: correctAnswer,
                itemLevel: item.level,
                candidates: candidates,
                mode: questionMode,
                supportLanguageCode: supportLanguageCode,
                using: &random
            )

            return QuizQuestion(
                id: "\(item.id)-\(questionMode.rawValue)",
                itemID: item.id,
                mode: questionMode,
                prompt: prompt(for: item, mode: questionMode, supportLanguageCode: supportLanguageCode),
                options: options,
                correctAnswer: correctAnswer,
                spokenText: questionMode == .listeningChoice ? item.pronunciationText : nil
            )
        }
    }

    func isCorrect(_ submittedAnswer: String, for question: QuizQuestion) -> Bool {
        guard question.mode == .spelling else {
            return submittedAnswer == question.correctAnswer
        }

        return submittedAnswer.trimmingCharacters(in: .whitespacesAndNewlines)
            .caseInsensitiveCompare(question.correctAnswer) == .orderedSame
    }

    private func prompt(
        for item: VocabularySeedItem,
        mode: PracticeMode,
        supportLanguageCode: String
    ) -> String {
        switch mode {
        case .expressionChoice:
            return item.plainExpression
        case .meaningChoice:
            return item.upgradedExpression
        case .listeningChoice:
            return ""
        case .spelling:
            return localizedMeaning(for: item, supportLanguageCode: supportLanguageCode)
        case .mixed:
            return ""
        }
    }

    private func answer(
        for item: VocabularySeedItem,
        mode: PracticeMode,
        supportLanguageCode: String
    ) -> String {
        switch mode {
        case .meaningChoice:
            return localizedMeaning(for: item, supportLanguageCode: supportLanguageCode)
        case .mixed, .expressionChoice, .listeningChoice, .spelling:
            return item.upgradedExpression
        }
    }

    private func localizedMeaning(for item: VocabularySeedItem, supportLanguageCode: String) -> String {
        item.meaning[supportLanguageCode] ?? item.meaning["en"] ?? ""
    }

    private func makeOptions<Random: RandomNumberGenerator>(
        correctAnswer: String,
        itemLevel: VocabularyLevel,
        candidates: [VocabularySeedItem],
        mode: PracticeMode,
        supportLanguageCode: String,
        using random: inout Random
    ) -> [String] {
        var seenAnswers = Set([correctAnswer])
        var distractors = candidates
            .filter { $0.level == itemLevel }
            .map { answer(for: $0, mode: mode, supportLanguageCode: supportLanguageCode) }
            .filter { seenAnswers.insert($0).inserted }

        distractors = shuffled(distractors, using: &random)
        return shuffled([correctAnswer] + distractors.prefix(3), using: &random)
    }

    private func shuffled<Element, Random: RandomNumberGenerator>(
        _ elements: some Sequence<Element>,
        using random: inout Random
    ) -> [Element] {
        var result = Array(elements)

        for index in result.indices.dropLast() {
            let randomIndex = index + randomOffset(upperBound: result.count - index, using: &random)
            result.swapAt(index, randomIndex)
        }

        return result
    }

    private func randomOffset<Random: RandomNumberGenerator>(
        upperBound: Int,
        using random: inout Random
    ) -> Int {
        let bound = UInt64(upperBound)
        let threshold = (0 &- bound) % bound
        var value = random.next()

        while value < threshold {
            value = random.next()
        }

        return Int(value % bound)
    }
}
