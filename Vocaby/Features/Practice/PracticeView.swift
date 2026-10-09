import AVFoundation
import SwiftData
import SwiftUI
import UIKit

private struct QuizShakeEffect: GeometryEffect {
    var animatableData: CGFloat

    func effectValue(size: CGSize) -> ProjectionTransform {
        let translation = animatableData == 0 ? 0 : 9 * sin(animatableData * .pi * 4)
        return ProjectionTransform(CGAffineTransform(translationX: translation, y: 0))
    }
}

struct ReviewPracticePlan {
    let runID: String
    let quizQuestions: [QuizQuestion]

    init(
        dayKey: String,
        items: [VocabularySeedItem],
        seedItems: [VocabularySeedItem],
        supportLanguageCode: String
    ) {
        var random = SystemRandomNumberGenerator()
        self.init(
            dayKey: dayKey,
            items: items,
            seedItems: seedItems,
            supportLanguageCode: supportLanguageCode,
            using: &random
        )
    }

    init<Random: RandomNumberGenerator>(
        dayKey: String,
        items: [VocabularySeedItem],
        seedItems: [VocabularySeedItem],
        supportLanguageCode: String,
        using random: inout Random
    ) {
        runID = ([dayKey] + items.map(\.id)).joined(separator: "#")
        quizQuestions = QuizEngine().makeQuestions(
            for: items,
            candidates: seedItems,
            mode: .mixed,
            supportLanguageCode: supportLanguageCode,
            using: &random
        )
    }
}

struct PracticeCenterPlan {
    static let defaultConfiguration = PracticeConfiguration(
        mode: .mixed,
        questionCount: 10,
        timeLimitSeconds: 15,
        retriesWrongAnswers: true
    )

    let runID: UUID
    let configuration: PracticeConfiguration
    let questions: [QuizQuestion]

    init(
        seedItems: [VocabularySeedItem],
        selectedLevel: VocabularyLevel,
        supportLanguageCode: String,
        learnedItemIDs: [String],
        configuration: PracticeConfiguration
    ) {
        var random = SystemRandomNumberGenerator()
        self.init(
            seedItems: seedItems,
            selectedLevel: selectedLevel,
            supportLanguageCode: supportLanguageCode,
            learnedItemIDs: learnedItemIDs,
            configuration: configuration,
            using: &random
        )
    }

    init<Random: RandomNumberGenerator>(
        seedItems: [VocabularySeedItem],
        selectedLevel: VocabularyLevel,
        supportLanguageCode: String,
        learnedItemIDs: [String],
        configuration: PracticeConfiguration,
        using random: inout Random
    ) {
        let pool = seedItems.filter {
            $0.level == selectedLevel && $0.supportLanguageCodes.contains(supportLanguageCode)
        }
        let selectedItems = QuizEngine().selectPracticeItems(
            from: pool,
            learnedItemIDs: learnedItemIDs,
            count: configuration.questionCount,
            using: &random
        )

        runID = UUID()
        self.configuration = configuration
        questions = QuizEngine().makeQuestions(
            for: selectedItems,
            candidates: pool,
            mode: configuration.mode,
            supportLanguageCode: supportLanguageCode,
            using: &random
        )
    }
}

struct PracticeCenterView: View {
    @Environment(\.appClock) private var clock
    @Environment(\.modelContext) private var modelContext

    let seedItems: [VocabularySeedItem]
    let selectedLevel: VocabularyLevel
    let supportLanguageCode: String
    let startsImmediately: Bool
    let onUpdate: () -> Void

    @State private var configuration = PracticeCenterPlan.defaultConfiguration
    @State private var activePlan: PracticeCenterPlan?
    @State private var loadError: String?

    private let reviewScheduler = ReviewScheduler()

    init(
        seedItems: [VocabularySeedItem],
        selectedLevel: VocabularyLevel,
        supportLanguageCode: String,
        startsImmediately: Bool = false,
        onUpdate: @escaping () -> Void = {}
    ) {
        self.seedItems = seedItems
        self.selectedLevel = selectedLevel
        self.supportLanguageCode = supportLanguageCode
        self.startsImmediately = startsImmediately
        self.onUpdate = onUpdate
    }

    private var hasEligibleItems: Bool {
        seedItems.contains {
            $0.level == selectedLevel && $0.supportLanguageCodes.contains(supportLanguageCode)
        }
    }

    var body: some View {
        Group {
            if let activePlan {
                QuizRunView(
                    runID: activePlan.runID,
                    questions: activePlan.questions,
                    configuration: activePlan.configuration,
                    tint: AppTheme.accent,
                    clock: clock,
                    onAttempt: persistAnswer
                ) {
                    Section {
                        Button {
                            self.activePlan = nil
                        } label: {
                            Text("practice.center.newRun")
                                .frame(maxWidth: .infinity, minHeight: 44)
                        }
                        .buttonStyle(.plain)
                    }
                }
            } else {
                setupForm
            }
        }
        .navigationTitle("practice.center.title")
        .task {
            if startsImmediately, activePlan == nil {
                startRun()
            }
        }
    }

    private var setupForm: some View {
        Form {
            Section {
                Picker("practice.center.mode.label", selection: $configuration.mode) {
                    ForEach(PracticeMode.allCases) { mode in
                        Text(modeTitleKey(for: mode)).tag(mode)
                    }
                }

                Picker("practice.center.questions.label", selection: $configuration.questionCount) {
                    ForEach(PracticeConfiguration.questionCounts, id: \.self) { count in
                        Text(verbatim: "\(count)").tag(count)
                    }
                }

                Picker("practice.center.timer.label", selection: $configuration.timeLimitSeconds) {
                    ForEach(PracticeConfiguration.timeLimits, id: \.self) { seconds in
                        (Text(verbatim: "\(seconds) ") + Text("practice.timer.seconds"))
                            .tag(seconds)
                    }
                }

                Toggle("practice.center.retry.toggle", isOn: $configuration.retriesWrongAnswers)
            }

            Section {
                Button {
                    startRun()
                } label: {
                    Text("practice.center.start")
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .prominentActionStyle(tint: AppTheme.accent)
                .disabled(!hasEligibleItems)
            }

            if let loadError {
                Section {
                    Text(loadError)
                        .foregroundStyle(AppTheme.wrongRed)
                }
            }
        }
    }

    private func modeTitleKey(for mode: PracticeMode) -> LocalizedStringKey {
        switch mode {
        case .mixed: "practice.center.mode.mixed"
        case .expressionChoice: "practice.center.mode.expression"
        case .meaningChoice: "practice.center.mode.meaning"
        case .listeningChoice: "practice.center.mode.listening"
        case .spelling: "practice.center.mode.spelling"
        }
    }

    private func startRun() {
        do {
            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            activePlan = PracticeCenterPlan(
                seedItems: seedItems,
                selectedLevel: selectedLevel,
                supportLanguageCode: supportLanguageCode,
                learnedItemIDs: progressRows.compactMap { $0.firstSeenAt == nil ? nil : $0.itemID },
                configuration: configuration
            )
            loadError = nil
        } catch {
            loadError = String(localized: "practice.center.load.error")
        }
    }

    private func persistAnswer(_ attempt: QuizAttempt) throws {
        guard let activePlan,
              let item = seedItems.first(where: { $0.id == attempt.question.itemID }) else {
            throw CocoaError(.fileReadCorruptFile)
        }

        try AnswerRecorder(scheduler: reviewScheduler).record(
            attempt.recordedAnswer(level: item.level),
            from: .freePractice(runID: activePlan.runID.uuidString),
            at: clock.now(),
            in: modelContext
        )
        onUpdate()
    }
}

struct QuizRunView<Completion: View>: View {
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    let runID: AnyHashable
    let questions: [QuizQuestion]
    let configuration: PracticeConfiguration
    let tint: Color
    let onAttempt: (QuizAttempt) throws -> Void
    let completion: () -> Completion
    private let clock: AppClock

    @State private var runState: QuizRunState
    @State private var spellingText = ""
    @State private var deadline: Date
    @State private var errorMessage: String?
    @State private var feedbackAnimationTrigger = 0
    @State private var shakeTrigger = 0
    @State private var runStartedAt: Date
    @State private var speechSynthesizer = AVSpeechSynthesizer()
    @FocusState private var isSpellingFocused: Bool

    init<RunID: Hashable>(
        runID: RunID,
        questions: [QuizQuestion],
        configuration: PracticeConfiguration,
        tint: Color,
        clock: AppClock,
        onAttempt: @escaping (QuizAttempt) throws -> Void,
        @ViewBuilder completion: @escaping () -> Completion
    ) {
        self.runID = AnyHashable(runID)
        self.questions = questions
        self.configuration = configuration
        self.tint = tint
        self.onAttempt = onAttempt
        self.completion = completion
        self.clock = clock
        _runState = State(initialValue: QuizRunState(questions: questions))
        _deadline = State(initialValue: clock.now().addingTimeInterval(TimeInterval(configuration.timeLimitSeconds)))
        _runStartedAt = State(initialValue: clock.now())
    }

    var body: some View {
        List {
            if runState.questions.isEmpty {
                completion()
            } else if let question = runState.currentQuestion {
                questionContent(question)
            } else {
                resultContent
            }

            if dynamicTypeSize.isAccessibilitySize, runState.currentFeedback != nil {
                Section {
                    nextButton
                }
            }

            if let errorMessage {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(AppTheme.wrongRed)
                }
            }
        }
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom) {
            if !dynamicTypeSize.isAccessibilitySize, runState.currentFeedback != nil {
                nextButton
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .bottomActionChrome()
            }
        }
        .onChange(of: runID) {
            resetRun()
        }
        .modifier(QuizShakeEffect(animatableData: CGFloat(shakeTrigger)))
    }

    private var nextButton: some View {
        Button {
            advance()
        } label: {
            Text("practice.next")
                .frame(maxWidth: .infinity)
        }
        .prominentActionStyle(tint: tint)
        .controlSize(.large)
    }

    @ViewBuilder
    private func questionContent(_ question: QuizQuestion) -> some View {
        Section {
            HStack(alignment: .firstTextBaseline) {
                Text("\(runState.currentIndex + 1)/\(runState.questions.count)")
                    .font(.headline.monospacedDigit())

                Spacer()

                if runState.currentFeedback == nil, configuration.timeLimitSeconds > 0 {
                    TimelineView(.periodic(from: .now, by: 1)) { _ in
                        // TimelineView 只負責每秒重算;「現在」一律走 clock,固定時鐘下倒數才會凍結而不是歸零
                        let remaining = max(0, Int(ceil(deadline.timeIntervalSince(clock.now()))))

                        VStack(alignment: .trailing, spacing: 4) {
                            HStack(spacing: 4) {
                                Image(systemName: "clock")
                                    .accessibilityHidden(true)
                                Text(formattedRemainingTime(remaining))
                                    .monospacedDigit()
                            }
                            ProgressView(
                                value: Double(remaining),
                                total: Double(max(configuration.timeLimitSeconds, 1))
                            )
                            .tint(Double(remaining) / Double(max(configuration.timeLimitSeconds, 1)) < 0.3
                                ? AppTheme.wrongRed
                                : tint)
                            .frame(width: 112)
                        }
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(Text("practice.timer.label"))
                        .accessibilityValue(Text("\(remaining) ") + Text("practice.timer.seconds"))
                        .onChange(of: remaining, initial: true) { _, remaining in
                            if remaining == 0 {
                                isSpellingFocused = false
                                if runState.timeout() != nil {
                                    feedbackAnimationTrigger += 1
                                    withAnimation(.linear(duration: 0.45)) { shakeTrigger += 1 }
                                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                                }
                            }
                        }
                    }
                }
            }

            VStack(alignment: .leading, spacing: 12) {
                Text(promptKey(for: question.mode))
                    .font(.headline)

                if question.mode == .listeningChoice {
                    Button {
                        speak(question)
                    } label: {
                        Image(systemName: "speaker.wave.3.fill")
                            .font(.title2)
                    }
                    .buttonStyle(.plain)
                    .minimumInteractiveSize()
                    .accessibilityLabel(Text("practice.audio.replay"))
                } else {
                    HStack(alignment: .top, spacing: 12) {
                        Text(verbatim: question.prompt)
                            .font(.title2.bold())

                        Spacer(minLength: 8)

                        Button {
                            speak(question)
                        } label: {
                            Image(systemName: "speaker.wave.2")
                        }
                        .buttonStyle(.plain)
                        .minimumInteractiveSize()
                        .accessibilityLabel(Text(audioLabelKey(for: question.mode)))
                    }
                }
            }
            .padding(.vertical, 4)

            if question.mode == .spelling {
                TextField("practice.spelling.placeholder", text: $spellingText)
                    .keyboardType(.asciiCapable)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
                    .focused($isSpellingFocused)
                    .disabled(runState.currentFeedback != nil)
                    .accessibilityLabel(Text("practice.mode.spelling.prompt"))
                    .onSubmit(submitSpelling)

                if runState.currentFeedback == nil {
                    Button("practice.submit", action: submitSpelling)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .prominentActionStyle(tint: tint)
                        .disabled(spellingText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            } else {
                ForEach(visibleOptions(for: question), id: \.self) { option in
                    Button {
                        submitWithFeedback(option)
                    } label: {
                        HStack(spacing: 12) {
                            Text(verbatim: option)
                                .foregroundStyle(optionColor(for: option, question: question))
                                .multilineTextAlignment(.leading)
                                .fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 8)
                            answerIcon(for: option, question: question)
                        }
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .disabled(runState.currentFeedback != nil)
                    .accessibilityLabel(Text(verbatim: option))
                }
            }

            if let feedback = runState.currentFeedback {
                Label {
                    Text(String(localized: feedback.timedOut
                        ? "practice.timeUp"
                        : feedback.wasCorrect ? "practice.correct" : "practice.wrong"))
                } icon: {
                    Image(systemName: feedback.wasCorrect ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .symbolEffect(.bounce, value: feedbackAnimationTrigger)
                }
                .font(.headline)
                .foregroundStyle(feedback.wasCorrect ? AppTheme.correctGreen : AppTheme.wrongRed)

                if !feedback.wasCorrect {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(verbatim: feedback.question.item.upgradedExpression)
                            .font(.title3.bold())
                        Text(verbatim: localized(
                            feedback.question.selectedSense.meaning,
                            languageCode: feedback.question.supportLanguageCode
                        ))
                        .fontWeight(.semibold)
                        Text(verbatim: feedback.question.selectedSense.example.text)
                        Text(verbatim: localized(
                            feedback.question.selectedSense.example.translation,
                            languageCode: feedback.question.supportLanguageCode
                        ))
                        .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    @ViewBuilder
    private var resultContent: some View {
        let scoredAttempts = runState.firstAttempts
        let correctCount = scoredAttempts.filter(\.wasCorrect).count
        let wrongAttempts = runState.isRetryRound
            ? runState.retryAttempts.filter { !$0.wasCorrect }
            : runState.firstAttempts.filter { !$0.wasCorrect }

        Section {
            HStack(spacing: 24) {
                Gauge(value: Double(correctCount), in: 0...Double(max(scoredAttempts.count, 1))) {
                    Text("practice.result.title")
                } currentValueLabel: {
                    Text("\(Int(Double(correctCount) / Double(max(scoredAttempts.count, 1)) * 100))%")
                        .font(.headline.monospacedDigit())
                }
                .gaugeStyle(.accessoryCircularCapacity)
                .tint(AppTheme.accent)
                .scaleEffect(1.35)
                .frame(width: 96, height: 96)

                VStack(alignment: .leading, spacing: 8) {
                    Label("\(correctCount)", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(AppTheme.correctGreen)
                    Label("\(scoredAttempts.count - correctCount)", systemImage: "xmark.circle.fill")
                        .foregroundStyle(AppTheme.wrongRed)
                    Label(formattedRemainingTime(Int(clock.now().timeIntervalSince(runStartedAt))), systemImage: "timer")
                        .foregroundStyle(.secondary)
                }
                .font(.headline.monospacedDigit())
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .combine)
        }

        if !wrongAttempts.isEmpty {
            Section("practice.result.wrong.title") {
                ForEach(Array(wrongAttempts.enumerated()), id: \.offset) { _, attempt in
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Image(systemName: "xmark.circle")
                            .foregroundStyle(AppTheme.wrongRed)
                            .accessibilityHidden(true)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(verbatim: attempt.question.item.upgradedExpression)
                                .fontWeight(.semibold)
                            Text(verbatim: localized(
                                attempt.question.selectedSense.meaning,
                                languageCode: attempt.question.supportLanguageCode
                            ))
                            .foregroundStyle(.secondary)
                        }
                    }
                }
            }

            if configuration.retriesWrongAnswers {
                Section {
                    Button {
                        startRetry()
                    } label: {
                        Text("practice.retry.button")
                            .frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .prominentActionStyle(tint: tint)
                }
            }
        }

        completion()
    }

    @ViewBuilder
    private func answerIcon(for option: String, question: QuizQuestion) -> some View {
        if runState.currentFeedback != nil, option == question.correctAnswer {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(AppTheme.correctGreen)
                .accessibilityHidden(true)
        } else if let feedback = runState.currentFeedback,
                  !feedback.wasCorrect,
                  option == feedback.submittedAnswer {
            Image(systemName: "xmark.circle.fill")
                .foregroundStyle(AppTheme.wrongRed)
                .accessibilityHidden(true)
        }
    }

    private func optionColor(for option: String, question: QuizQuestion) -> Color {
        guard let feedback = runState.currentFeedback else { return .primary }
        if option == question.correctAnswer { return AppTheme.correctGreen }
        if !feedback.wasCorrect, option == feedback.submittedAnswer { return AppTheme.wrongRed }
        return .secondary
    }

    private func visibleOptions(for question: QuizQuestion) -> [String] {
        guard let feedback = runState.currentFeedback else {
            return question.options
        }

        var options: [String] = []
        if !feedback.submittedAnswer.isEmpty {
            options.append(feedback.submittedAnswer)
        }
        if !options.contains(question.correctAnswer) {
            options.append(question.correctAnswer)
        }
        return options
    }

    private func formattedRemainingTime(_ seconds: Int) -> String {
        String(format: "%d:%02d", seconds / 60, seconds % 60)
    }

    private func localized(_ values: [String: String], languageCode: String) -> String {
        values[languageCode] ?? values["en"] ?? values.values.first ?? ""
    }

    private func promptKey(for mode: PracticeMode) -> LocalizedStringKey {
        switch mode {
        case .expressionChoice: "practice.mode.expression.prompt"
        case .meaningChoice: "practice.mode.meaning.prompt"
        case .listeningChoice: "practice.mode.listening.prompt"
        case .spelling: "practice.mode.spelling.prompt"
        case .mixed: "practice.mode.expression.prompt"
        }
    }

    private func audioLabelKey(for mode: PracticeMode) -> LocalizedStringKey {
        mode == .spelling ? "practice.spelling.audioHint" : "practice.audio.play"
    }

    private func submitSpelling() {
        guard !spellingText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        isSpellingFocused = false
        submitWithFeedback(spellingText)
    }

    private func submitWithFeedback(_ answer: String) {
        guard let attempt = runState.submit(answer) else { return }
        feedbackAnimationTrigger += 1
        if !attempt.wasCorrect {
            withAnimation(.linear(duration: 0.45)) { shakeTrigger += 1 }
        }
        UINotificationFeedbackGenerator().notificationOccurred(attempt.wasCorrect ? .success : .error)
    }

    private func advance() {
        guard let feedback = runState.currentFeedback else { return }

        do {
            try onAttempt(feedback)
        } catch {
            errorMessage = String(localized: "practice.save.error")
            return
        }

        runState.advance()
        spellingText = ""
        isSpellingFocused = false
        errorMessage = nil
        resetDeadline()
    }

    private func startRetry() {
        guard runState.startRetry() else { return }
        spellingText = ""
        isSpellingFocused = false
        errorMessage = nil
        resetDeadline()
    }

    private func resetDeadline() {
        guard configuration.timeLimitSeconds > 0 else { return }
        deadline = clock.now().addingTimeInterval(TimeInterval(configuration.timeLimitSeconds))
    }

    private func resetRun() {
        runState.reset(with: questions)
        runStartedAt = clock.now()
        spellingText = ""
        isSpellingFocused = false
        errorMessage = nil
        resetDeadline()
    }

    private func speak(_ question: QuizQuestion) {
        if question.mode == .expressionChoice {
            let utterance = AVSpeechUtterance(string: question.pronunciationText)
            utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
            speechSynthesizer.speak(utterance)
            return
        }

        guard let pronunciationID = question.selectedSense.pronunciationIDs.first,
              let pronunciation = question.item.pronunciations.first(where: { $0.id == pronunciationID }) else {
            return
        }
        speechSynthesizer.speak(PronunciationSpeaker.makeUtterance(
            expression: question.pronunciationText,
            pronunciation: pronunciation
        ))
    }
}
