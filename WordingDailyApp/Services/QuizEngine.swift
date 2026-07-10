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

struct QuizAttempt: Equatable {
    let question: QuizQuestion
    let submittedAnswer: String
    let wasCorrect: Bool
    let timedOut: Bool
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

        return items.enumerated().map { index, item in
            let questionMode = mode == .mixed ? concreteModes[index % concreteModes.count] : mode
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
