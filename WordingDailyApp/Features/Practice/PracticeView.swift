import AVFoundation
import SwiftUI

struct QuizRunView<Completion: View>: View {
    let configuration: PracticeConfiguration
    let tint: Color
    let onFirstAttempt: (QuizAttempt) throws -> Void
    let completion: () -> Completion

    @State private var runState: QuizRunState
    @State private var spellingText = ""
    @State private var deadline: Date
    @State private var errorMessage: String?
    @State private var speechSynthesizer = AVSpeechSynthesizer()

    init(
        questions: [QuizQuestion],
        configuration: PracticeConfiguration,
        tint: Color,
        onFirstAttempt: @escaping (QuizAttempt) throws -> Void,
        @ViewBuilder completion: @escaping () -> Completion
    ) {
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

    private func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        speechSynthesizer.speak(utterance)
    }
}
