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
                seedItems: seedItems,
                dayKey: dayKeyService.dayKey(for: Date()),
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
    let seedItems: [VocabularySeedItem]
    let dayKey: String
    let supportLanguageCode: String
    let onUpdate: () -> Void

    private let dayKeyService = DayKeyService()
    private let persistenceService = ProgressPersistenceService()
    private let reviewScheduler = ReviewScheduler()

    var body: some View {
        let plan = ReviewPracticePlan(
            dayKey: dayKey,
            items: items,
            seedItems: seedItems,
            supportLanguageCode: supportLanguageCode
        )

        QuizRunView(
            runID: plan.runID,
            questions: plan.quizQuestions,
            configuration: PracticeConfiguration(
                mode: .mixed,
                questionCount: plan.quizQuestions.count,
                timeLimitSeconds: 15,
                retriesWrongAnswers: true
            ),
            tint: AppTheme.reviewAmber,
            onFirstAttempt: persistAnswer
        ) {
            completionContent
        }
        .navigationTitle("review.session.title")
        .onDisappear {
            onUpdate()
        }
    }

    @ViewBuilder
    private var completionContent: some View {
        Section {
            Text("review.completed")
                .font(.headline)

            Button("common.done") {
                dismiss()
            }
        }
    }

    private func persistAnswer(_ attempt: QuizAttempt) throws {
        guard attempt.isFirstAttempt,
              let item = items.first(where: { $0.id == attempt.question.itemID }) else {
            throw CocoaError(.fileReadCorruptFile)
        }

        do {
            let now = Date()
            let indices = attempt.question.persistenceIndices(
                for: attempt.submittedAnswer,
                wasCorrect: attempt.wasCorrect
            )
            let progress = try persistenceService.wordProgress(
                for: item.id,
                level: item.level,
                in: modelContext
            )
            reviewScheduler.applyAnswer(
                to: progress,
                wasCorrect: attempt.wasCorrect,
                answeredAt: now,
                context: .review
            )
            _ = try persistenceService.quizResult(
                dayKey: dayKeyService.dayKey(for: now),
                itemID: item.id,
                selectedOptionIndex: indices.selected,
                correctOptionIndex: indices.correct,
                in: modelContext
            )
            if modelContext.hasChanges {
                try modelContext.save()
            }
        } catch {
            modelContext.rollback()
            throw error
        }
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
