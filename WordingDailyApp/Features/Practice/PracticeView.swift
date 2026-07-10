import AVFoundation
import SwiftData
import SwiftUI

struct DailyPracticePlan {
    let runID: String
    let learnItems: [VocabularySeedItem]
    let quizQuestions: [QuizQuestion]

    init(
        session: DailySession,
        seedItems: [VocabularySeedItem],
        supportLanguageCode: String
    ) {
        runID = session.dayKey

        let seedByID = Dictionary(uniqueKeysWithValues: seedItems.map { ($0.id, $0) })
        let unansweredItems = session.items
            .filter { $0.answeredAt == nil }
            .sorted { $0.position < $1.position }

        learnItems = unansweredItems
            .filter { !$0.isReviewFill }
            .compactMap { seedByID[$0.itemID] }
        quizQuestions = QuizEngine().makeQuestions(
            for: unansweredItems.compactMap { seedByID[$0.itemID] },
            candidates: seedItems,
            mode: .mixed,
            supportLanguageCode: supportLanguageCode
        )
    }
}

struct QuizRunView<Completion: View>: View {
    let runID: AnyHashable
    let questions: [QuizQuestion]
    let configuration: PracticeConfiguration
    let tint: Color
    let onFirstAttempt: (QuizAttempt) throws -> Void
    let completion: () -> Completion

    @State private var runState: QuizRunState
    @State private var spellingText = ""
    @State private var deadline: Date
    @State private var errorMessage: String?
    @State private var speechSynthesizer = AVSpeechSynthesizer()

    init<RunID: Hashable>(
        runID: RunID,
        questions: [QuizQuestion],
        configuration: PracticeConfiguration,
        tint: Color,
        onFirstAttempt: @escaping (QuizAttempt) throws -> Void,
        @ViewBuilder completion: @escaping () -> Completion
    ) {
        self.runID = AnyHashable(runID)
        self.questions = questions
        self.configuration = configuration
        self.tint = tint
        self.onFirstAttempt = onFirstAttempt
        self.completion = completion
        _runState = State(initialValue: QuizRunState(questions: questions))
        _deadline = State(initialValue: Date().addingTimeInterval(TimeInterval(configuration.timeLimitSeconds)))
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

            if let errorMessage {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(AppTheme.wrongRed)
                }
            }
        }
        .safeAreaInset(edge: .bottom) {
            if runState.currentFeedback != nil {
                Button {
                    advance()
                } label: {
                    Text("practice.next")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .tint(tint)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(.regularMaterial)
            }
        }
        .onChange(of: runID) {
            resetRun()
        }
    }

    @ViewBuilder
    private func questionContent(_ question: QuizQuestion) -> some View {
        Section {
            HStack(alignment: .firstTextBaseline) {
                Text("\(runState.currentIndex + 1)/\(runState.questions.count)")
                    .font(.headline.monospacedDigit())

                Spacer()

                if runState.currentFeedback == nil {
                    TimelineView(.periodic(from: .now, by: 1)) { context in
                        let remaining = max(0, Int(ceil(deadline.timeIntervalSince(context.date))))

                        HStack(spacing: 4) {
                            Text("practice.timer.label")
                            Text("\(remaining)")
                                .monospacedDigit()
                        }
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(Text("practice.timer.label"))
                        .accessibilityValue(Text("\(remaining) ") + Text("practice.timer.seconds"))
                        .onChange(of: remaining, initial: true) { _, remaining in
                            if remaining == 0 {
                                _ = runState.timeout()
                            }
                        }
                    }
                }
            }

            VStack(alignment: .leading, spacing: 12) {
                Text(promptKey(for: question.mode))
                    .font(.headline)

                if question.mode == .listeningChoice {
                    if let spokenText = question.spokenText {
                        Button {
                            speak(spokenText)
                        } label: {
                            Label("practice.audio.replay", systemImage: "speaker.wave.2")
                                .frame(minWidth: 44, minHeight: 44)
                        }
                        .buttonStyle(.bordered)
                        .accessibilityLabel(Text("practice.audio.replay"))
                    }
                } else {
                    Text(verbatim: question.prompt)
                        .font(.title2.bold())
                }
            }
            .padding(.vertical, 4)
        }

        if question.mode == .spelling {
            Section {
                TextField("practice.spelling.placeholder", text: $spellingText)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
                    .disabled(runState.currentFeedback != nil)
                    .accessibilityLabel(Text("practice.mode.spelling.prompt"))
                    .onSubmit(submitSpelling)

                if runState.currentFeedback == nil {
                    Button("practice.submit", action: submitSpelling)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .buttonStyle(.borderedProminent)
                        .tint(tint)
                        .disabled(spellingText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        } else {
            Section {
                ForEach(question.options, id: \.self) { option in
                    Button {
                        _ = runState.submit(option)
                    } label: {
                        HStack(spacing: 12) {
                            Text(verbatim: option)
                                .multilineTextAlignment(.leading)
                                .fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 8)
                            answerIcon(for: option, question: question)
                        }
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.bordered)
                    .tint(optionTint(for: option, question: question))
                    .disabled(runState.currentFeedback != nil)
                    .accessibilityLabel(Text(verbatim: option))
                }
            }
        }

        if let feedback = runState.currentFeedback {
            Section {
                Label {
                    Text(String(localized: feedback.timedOut
                        ? "practice.timeUp"
                        : feedback.wasCorrect ? "practice.correct" : "practice.wrong"))
                } icon: {
                    Image(systemName: feedback.wasCorrect ? "checkmark.circle.fill" : "xmark.circle.fill")
                }
                .font(.headline)
                .foregroundStyle(feedback.wasCorrect ? AppTheme.correctGreen : AppTheme.wrongRed)

                if !feedback.wasCorrect {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("practice.correctAnswer.label")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Text(verbatim: feedback.question.correctAnswer)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var resultContent: some View {
        let wrongAttempts = runState.isRetryRound
            ? runState.retryAttempts.filter { !$0.wasCorrect }
            : runState.firstAttempts.filter { !$0.wasCorrect }

        Section {
            Text("practice.result.title")
                .font(.headline)
        }

        if !wrongAttempts.isEmpty {
            Section("practice.result.wrong.title") {
                ForEach(Array(wrongAttempts.enumerated()), id: \.offset) { _, attempt in
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Image(systemName: "xmark.circle")
                            .foregroundStyle(AppTheme.wrongRed)
                            .accessibilityHidden(true)
                        VStack(alignment: .leading, spacing: 4) {
                            if !attempt.question.prompt.isEmpty {
                                Text(verbatim: attempt.question.prompt)
                                    .foregroundStyle(.secondary)
                            }
                            Text(verbatim: attempt.question.correctAnswer)
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
                    .buttonStyle(.borderedProminent)
                    .tint(tint)
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

    private func optionTint(for option: String, question: QuizQuestion) -> Color {
        guard let feedback = runState.currentFeedback else { return tint }
        if option == question.correctAnswer { return AppTheme.correctGreen }
        if !feedback.wasCorrect, option == feedback.submittedAnswer { return AppTheme.wrongRed }
        return tint
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

    private func submitSpelling() {
        guard !spellingText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        _ = runState.submit(spellingText)
    }

    private func advance() {
        guard let feedback = runState.currentFeedback else { return }

        if feedback.isFirstAttempt {
            do {
                try onFirstAttempt(feedback)
            } catch {
                errorMessage = String(localized: "practice.save.error")
                return
            }
        }

        runState.advance()
        spellingText = ""
        errorMessage = nil
        resetDeadline()
    }

    private func startRetry() {
        guard runState.startRetry() else { return }
        spellingText = ""
        errorMessage = nil
        resetDeadline()
    }

    private func resetDeadline() {
        deadline = Date().addingTimeInterval(TimeInterval(configuration.timeLimitSeconds))
    }

    private func resetRun() {
        runState.reset(with: questions)
        spellingText = ""
        errorMessage = nil
        resetDeadline()
    }

    private func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        speechSynthesizer.speak(utterance)
    }
}

struct DailyPracticeView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let session: DailySession
    let seedItems: [VocabularySeedItem]
    let supportLanguageCode: String
    let streakCount: Int
    let scheduledReviewCount: Int
    let dueReviewCount: Int
    let onReview: () -> Void
    let onUpdate: () -> Void

    @State private var learnIndex = 0
    @State private var speechSynthesizer = AVSpeechSynthesizer()

    private let persistenceService = ProgressPersistenceService()
    private let reviewScheduler = ReviewScheduler()

    var body: some View {
        let plan = DailyPracticePlan(
            session: session,
            seedItems: seedItems,
            supportLanguageCode: supportLanguageCode
        )

        Group {
            if plan.learnItems.indices.contains(learnIndex) {
                learnView(item: plan.learnItems[learnIndex], total: plan.learnItems.count)
            } else {
                QuizRunView(
                    runID: plan.runID,
                    questions: plan.quizQuestions,
                    configuration: .daily,
                    tint: AppTheme.accent,
                    onFirstAttempt: persistAnswer
                ) {
                    completionContent
                }
            }
        }
        .navigationTitle("practice.title")
    }

    private func learnView(item: VocabularySeedItem, total: Int) -> some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 16) {
                    Text("\(learnIndex + 1)/\(total)")
                        .font(.headline.monospacedDigit())

                    Text(verbatim: item.upgradedExpression)
                        .font(.title2.bold())

                    Text(verbatim: item.plainExpression)
                        .foregroundStyle(.secondary)

                    Text(verbatim: localized(item.meaning))

                    VStack(alignment: .leading, spacing: 4) {
                        Text(verbatim: item.example.text)
                        Text(verbatim: localized(item.example.translation))
                            .foregroundStyle(.secondary)
                    }
                    .font(.subheadline)

                    Button {
                        speak(item.pronunciationText)
                    } label: {
                        Label("practice.pronunciation.accessibility", systemImage: "speaker.wave.2")
                            .frame(minWidth: 44, minHeight: 44)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel(Text("practice.pronunciation.accessibility"))
                }
                .padding(.vertical, 8)
            }
        }
        .safeAreaInset(edge: .bottom) {
            Button {
                learnIndex += 1
            } label: {
                Group {
                    if learnIndex + 1 == total {
                        Text("practice.learn.startQuiz")
                    } else {
                        Text("practice.next")
                    }
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .tint(AppTheme.accent)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(.regularMaterial)
        }
    }

    @ViewBuilder
    private var completionContent: some View {
        Section {
            Label("practice.completed", systemImage: "checkmark.circle.fill")
                .font(.headline)
                .foregroundStyle(AppTheme.accent)

            LabeledContent("practice.completed.count", value: "\(session.completedItemCount)")
            LabeledContent("practice.correct.count", value: "\(session.correctItemCount)")
            LabeledContent("practice.review.scheduled", value: "\(scheduledReviewCount)")
            LabeledContent("streak.label", value: "\(streakCount)")
        }

        Section {
            if dueReviewCount > 0 {
                Button {
                    dismiss()
                    onReview()
                } label: {
                    Label("practice.review.button", systemImage: "arrow.triangle.2.circlepath")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .tint(AppTheme.accent)
            }

            Button("common.done") {
                dismiss()
            }
        }
    }

    private func persistAnswer(_ attempt: QuizAttempt) throws {
        guard let sessionItem = session.items.first(where: {
            $0.itemID == attempt.question.itemID && $0.answeredAt == nil
        }), let seedItem = seedItems.first(where: { $0.id == attempt.question.itemID }) else {
            return
        }

        do {
            let progress = try persistenceService.wordProgress(
                for: seedItem.id,
                level: seedItem.level,
                in: modelContext
            )
            let now = Date()
            let indices = attempt.question.persistenceIndices(
                for: attempt.submittedAnswer,
                wasCorrect: attempt.wasCorrect
            )

            sessionItem.selectedOptionIndex = indices.selected
            sessionItem.wasCorrect = attempt.wasCorrect
            sessionItem.answeredAt = now
            reviewScheduler.applyAnswer(
                to: progress,
                wasCorrect: attempt.wasCorrect,
                answeredAt: now,
                context: sessionItem.reviewAnswerContext
            )
            if session.items.allSatisfy({ $0.answeredAt != nil }) {
                session.completedAt = now
            }

            _ = try persistenceService.quizResult(
                dayKey: session.dayKey,
                itemID: seedItem.id,
                selectedOptionIndex: indices.selected,
                correctOptionIndex: indices.correct,
                in: modelContext
            )
            if modelContext.hasChanges {
                try modelContext.save()
            }
            onUpdate()
        } catch {
            modelContext.rollback()
            throw error
        }
    }

    private func localized(_ values: [String: String]) -> String {
        values[supportLanguageCode] ?? values["en"] ?? values.values.first ?? ""
    }

    private func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        speechSynthesizer.speak(utterance)
    }
}
