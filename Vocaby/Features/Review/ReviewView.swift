import SwiftData
import SwiftUI

struct ReviewView: View {
    @Environment(\.appClock) private var clock
    @Environment(\.modelContext) private var modelContext
    @State private var isShowingReview = false
    @State private var seedItems: [VocabularySeedItem] = []
    @State private var dueItems: [VocabularySeedItem] = []
    @State private var statusMessage: String?

    private let contentLanguageCode = AppLanguage.content
    private let supportLanguageCode = AppLanguage.support
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
                dayKey: dayKeyService.dayKey(for: clock.now()),
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
            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            let dueProgressRows = reviewScheduler.dueItems(from: progressRows, at: clock.now(), limit: 20)
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
    @Environment(\.appClock) private var clock
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let items: [VocabularySeedItem]
    let seedItems: [VocabularySeedItem]
    let dayKey: String
    let supportLanguageCode: String
    let onUpdate: () -> Void

    private let dayKeyService = DayKeyService()
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
            clock: clock,
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

        let now = clock.now()
        try AnswerRecorder(scheduler: reviewScheduler).record(
            attempt.recordedAnswer(level: item.level),
            from: .review(runID: dayKey, resultDayKey: dayKeyService.dayKey(for: now)),
            at: now,
            in: modelContext
        )
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
