import AVFoundation
import SwiftData
import SwiftUI

struct ReviewView: View {
    @Environment(\.modelContext) private var modelContext
    @State private var isShowingReview = false
    @State private var seedItems: [VocabularySeedItem] = []
    @State private var dueItems: [VocabularySeedItem] = []
    @State private var statusMessage: String?

    private let contentLanguageCode = "en"
    private let supportLanguageCode = "zh-Hant"
    private let dayKeyService = DayKeyService()
    private let reviewQueueService = ReviewQueueService()
    private let reviewScheduler = ReviewScheduler()
    private let seedLoader = SeedLoader()

    var body: some View {
        List {
            Section {
                HStack(alignment: .firstTextBaseline) {
                    Text("review.due.title")
                        .font(.headline)
                    Spacer()
                    Text("\(dueItems.count)")
                        .font(.title3.monospacedDigit())
                        .foregroundStyle(AppTheme.reviewAmber)
                }

                Button {
                    isShowingReview = true
                } label: {
                    Label("review.start.button", systemImage: "arrow.triangle.2.circlepath")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .tint(AppTheme.reviewAmber)
                .disabled(dueItems.isEmpty)
            }

            if dueItems.isEmpty {
                Section {
                    Text("review.empty.message")
                        .foregroundStyle(.secondary)
                }
            } else {
                Section {
                    ForEach(dueItems.prefix(5)) { item in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(item.upgradedExpression)
                                .font(.headline)
                            Text(item.plainExpression)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 4)
                    }
                }
            }

            if let statusMessage {
                Section {
                    Text(statusMessage)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("review.title")
        .task {
            refreshReviewQueue()
        }
        .navigationDestination(isPresented: $isShowingReview) {
            ReviewSessionView(
                items: dueItems,
                supportLanguageCode: supportLanguageCode
            ) {
                refreshReviewQueue()
            }
        }
    }

    private func refreshReviewQueue() {
        do {
            try loadSeedIfNeeded()
            let dayKey = dayKeyService.dayKey(for: Date())
            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            let dueProgressRows = reviewScheduler.dueItems(from: progressRows, on: dayKey, limit: 20)
            dueItems = reviewQueueService.queuedItems(
                from: seedItems,
                dueProgressRows: dueProgressRows,
                contentLanguageCode: contentLanguageCode,
                supportLanguageCode: supportLanguageCode
            )
            statusMessage = nil
        } catch {
            statusMessage = String(localized: "review.load.error")
        }
    }

    private func loadSeedIfNeeded() throws {
        if seedItems.isEmpty {
            seedItems = try seedLoader.loadBundledSeed()
        }
    }
}

private struct ReviewSessionView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let items: [VocabularySeedItem]
    let supportLanguageCode: String
    let onUpdate: () -> Void

    @State private var currentIndex = 0
    @State private var selectedOptionIndex: Int?
    @State private var errorMessage: String?
    @State private var speechSynthesizer = AVSpeechSynthesizer()

    private let dayKeyService = DayKeyService()
    private let persistenceService = ProgressPersistenceService()
    private let reviewScheduler = ReviewScheduler()

    private var currentItem: VocabularySeedItem? {
        guard currentIndex < items.count else {
            return nil
        }

        return items[currentIndex]
    }

    private var isLastItem: Bool {
        currentIndex + 1 >= items.count
    }

    var body: some View {
        List {
            if let item = currentItem {
                Section {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            Text("\(currentIndex + 1)/\(max(items.count, 1))")
                                .font(.headline.monospacedDigit())
                            Spacer()
                            Button {
                                speak(item.pronunciationText)
                            } label: {
                                Label(item.pronunciationText, systemImage: "speaker.wave.2")
                            }
                            .buttonStyle(.bordered)
                            .accessibilityLabel(Text("practice.pronunciation.accessibility"))
                        }

                        Text(item.upgradedExpression)
                            .font(.title2.bold())

                        Text(item.plainExpression)
                            .font(.body)
                            .foregroundStyle(.secondary)

                        Text(localized(item.meaning))
                            .font(.body)

                        VStack(alignment: .leading, spacing: 4) {
                            Text(item.example.text)
                            Text(localized(item.example.translation))
                                .foregroundStyle(.secondary)
                        }
                        .font(.subheadline)
                    }
                    .padding(.vertical, 8)
                }

                Section {
                    Text(localized(item.quiz.prompt))
                        .font(.headline)

                    ForEach(Array(item.quiz.options.enumerated()), id: \.offset) { index, option in
                        Button {
                            selectedOptionIndex = index
                        } label: {
                            HStack {
                                Text(option)
                                    .multilineTextAlignment(.leading)
                                Spacer()
                                answerIcon(for: index, correctOptionIndex: item.quiz.correctOptionIndex)
                            }
                            .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        }
                        .buttonStyle(.bordered)
                        .tint(answerTint(for: index, correctOptionIndex: item.quiz.correctOptionIndex))
                        .disabled(selectedOptionIndex != nil)
                    }
                }

                if let selectedOptionIndex {
                    Section {
                        Text(String(localized: selectedOptionIndex == item.quiz.correctOptionIndex ? "practice.correct" : "practice.wrong"))
                            .font(.headline)

                        Button {
                            persistAnswer()
                        } label: {
                            Text(String(localized: isLastItem ? "common.done" : "practice.next"))
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        .tint(AppTheme.reviewAmber)
                    }
                }
            } else {
                Section {
                    Text("review.completed")
                        .font(.headline)

                    Button("common.done") {
                        dismiss()
                    }
                }
            }

            if let errorMessage {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("review.session.title")
        .onDisappear {
            onUpdate()
        }
    }

    @ViewBuilder
    private func answerIcon(for index: Int, correctOptionIndex: Int) -> some View {
        if selectedOptionIndex != nil && index == correctOptionIndex {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(AppTheme.correctGreen)
        } else if selectedOptionIndex == index {
            Image(systemName: "xmark.circle.fill")
                .foregroundStyle(AppTheme.wrongRed)
        }
    }

    private func answerTint(for index: Int, correctOptionIndex: Int) -> Color? {
        guard let selectedOptionIndex else {
            return nil
        }

        if index == correctOptionIndex {
            return AppTheme.correctGreen
        }

        return selectedOptionIndex == index ? AppTheme.wrongRed : nil
    }

    private func persistAnswer() {
        guard let item = currentItem, let selectedOptionIndex else {
            return
        }

        do {
            let now = Date()
            let wasCorrect = selectedOptionIndex == item.quiz.correctOptionIndex
            let progress = try persistenceService.wordProgress(for: item.id, level: item.level, in: modelContext)
            reviewScheduler.applyAnswer(
                to: progress,
                wasCorrect: wasCorrect,
                answeredAt: now,
                context: .review
            )
            _ = try persistenceService.quizResult(
                dayKey: dayKeyService.dayKey(for: now),
                itemID: item.id,
                selectedOptionIndex: selectedOptionIndex,
                correctOptionIndex: item.quiz.correctOptionIndex,
                in: modelContext
            )

            try modelContext.save()
            self.selectedOptionIndex = nil
            errorMessage = nil
            currentIndex += 1
        } catch {
            errorMessage = String(localized: "practice.save.error")
        }
    }

    private func localized(_ values: [String: String]) -> String {
        values[supportLanguageCode] ?? values.values.first ?? ""
    }

    private func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        speechSynthesizer.speak(utterance)
    }
}

#Preview {
    NavigationStack {
        ReviewView()
    }
    .modelContainer(for: [
        WordProgress.self,
        DailySession.self,
        DailySessionItem.self,
        QuizResult.self
    ], inMemory: true)
}
