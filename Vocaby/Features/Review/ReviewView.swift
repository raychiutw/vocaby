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

    private var estimatedMinutes: Int {
        max(1, dueItems.count / 3 + 1)
    }

    private var reviewSummary: String {
        String.localizedStringWithFormat(
            String(localized: "review.queue.summary.format"),
            dueItems.count,
            estimatedMinutes
        )
    }

    var body: some View {
        List {
            if dueItems.isEmpty {
                Section {
                    ContentUnavailableView(
                        "review.empty.title",
                        systemImage: "checkmark.circle",
                        description: Text("review.empty.description")
                    )
                    .frame(maxWidth: .infinity)
                    .listRowSeparator(.hidden)
                }
            } else {
                Section {
                    Text(reviewSummary)
                        .font(.title3.weight(.semibold))

                    Button {
                        isShowingReview = true
                    } label: {
                        Label("review.start.button", systemImage: "arrow.triangle.2.circlepath")
                            .frame(maxWidth: .infinity)
                    }
                    .prominentActionStyle(tint: AppTheme.reviewAmber)
                    .controlSize(.large)
                }

                Section("review.nextUp.title") {
                    ForEach(dueItems.prefix(3)) { item in
                        CompactMetadataRow(
                            title: item.upgradedExpression,
                            subtitle: item.plainExpression,
                            systemImage: "text.quote",
                            tint: AppTheme.reviewAmber
                        )
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
        .listStyle(.plain)
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
        .learningSettingsSheet()
    }

    private func refreshReviewQueue() {
        do {
            try loadSeedIfNeeded()
            let dayKey = dayKeyService.dayKey(for: Date())
            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            let dueProgressRows = reviewScheduler.dueItems(from: progressRows, at: Date(), limit: 20)
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
            onAttempt: persistAnswer
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
            Button("common.done") {
                dismiss()
            }
        }
    }

    private func persistAnswer(_ attempt: QuizAttempt) throws {
        guard let item = items.first(where: { $0.id == attempt.question.itemID }) else {
            throw CocoaError(.fileReadCorruptFile)
        }

        do {
            let now = Date()
            if attempt.isFirstAttempt {
                let indices = attempt.question.persistenceIndices(
                    for: attempt.submittedAnswer,
                    wasCorrect: attempt.wasCorrect
                )
                guard let progress = try persistenceService.existingWordProgress(
                    for: item.id,
                    in: modelContext
                ) else {
                    throw CocoaError(.fileReadCorruptFile)
                }
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
            }

            _ = try persistenceService.practiceAttempt(
                runID: dayKey,
                itemID: item.id,
                level: item.level,
                mode: attempt.question.mode,
                wasCorrect: attempt.wasCorrect,
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
        QuizResult.self,
        PracticeAttemptRecord.self
    ], inMemory: true)
}
