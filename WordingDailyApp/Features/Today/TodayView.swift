import SwiftData
import SwiftUI
import WidgetKit

struct TodayView: View {
    @Environment(\.modelContext) private var modelContext
    @State private var isShowingSettings = false
    @State private var isShowingPractice = false
    @State private var todaySession: DailySession?
    @State private var seedItems: [VocabularySeedItem] = []
    @State private var dueReviewCount = 0
    @State private var scheduledReviewCount = 0
    @State private var streakCount = 0
    @State private var statusMessage: String?

    let onReview: () -> Void

    private let contentLanguageCode = "en"
    private let supportLanguageCode = "zh-Hant"
    private let dailyTargetCount = 10
    private let dayKeyService = DayKeyService()
    private let dailySelectionService = DailySelectionService()
    private let persistenceService = ProgressPersistenceService()
    private let preferencesStore = UserPreferencesStore()
    private let reviewScheduler = ReviewScheduler()
    private let seedLoader = SeedLoader()
    private let streakService = StreakService()
    private let widgetSnapshotWriter = WidgetSnapshotWriter.appGroupWriter()

    private var orderedSessionItems: [DailySessionItem] {
        (todaySession?.items ?? []).sorted { $0.position < $1.position }
    }

    private var completedCount: Int {
        todaySession?.completedItemCount ?? 0
    }

    private var totalCount: Int {
        let itemCount = orderedSessionItems.count
        return itemCount > 0 ? itemCount : dailyTargetCount
    }

    private var progressText: String {
        "\(completedCount)/\(totalCount)"
    }

    private var previewText: String {
        guard let previewItem = nextSeedItem else {
            return String(localized: "today.preview.empty")
        }

        return previewItem.upgradedExpression
    }

    private var nextSeedItem: VocabularySeedItem? {
        let seedByID = Dictionary(uniqueKeysWithValues: seedItems.map { ($0.id, $0) })
        return orderedSessionItems
            .first { $0.answeredAt == nil }
            .flatMap { seedByID[$0.itemID] }
    }

    private var primaryButtonTitle: LocalizedStringKey {
        guard todaySession != nil else {
            return "today.start.button"
        }

        return completedCount == totalCount ? "today.completed.button" : "today.resume.button"
    }

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    Text(Date.now, style: .date)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    LabeledContent("streak.label", value: "\(streakCount)")
                        .monospacedDigit()
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    HStack(alignment: .firstTextBaseline) {
                        Text("today.progress.title")
                            .font(.headline)
                        Spacer()
                        Text(progressText)
                            .font(.headline.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }

                    ProgressView(value: Double(completedCount), total: Double(totalCount))
                        .tint(AppTheme.accent)
                        .accessibilityLabel(Text("today.progress.accessibility"))
                        .accessibilityValue(Text(progressText))

                    Button {
                        startPractice()
                    } label: {
                        Text(primaryButtonTitle)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(AppTheme.accent)
                    .disabled(todaySession != nil && completedCount == totalCount)
                    .accessibilityIdentifier("today.start")
                }
                .padding(.vertical, 8)
            }

            Section {
                LabeledContent("today.due.label", value: "\(dueReviewCount)")
                LabeledContent("today.preview.label", value: previewText)
            }

            Section {
                NavigationLink {
                    PracticeCenterView(
                        seedItems: seedItems,
                        selectedLevel: preferencesStore.read().selectedLevel,
                        supportLanguageCode: supportLanguageCode
                    )
                } label: {
                    Label("practice.center.button", systemImage: "slider.horizontal.3")
                }
            }

            if let statusMessage {
                Section {
                    Text(statusMessage)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("today.title")
        .task {
            refreshToday()
        }
        .navigationDestination(isPresented: $isShowingPractice) {
            if let todaySession {
                DailyPracticeView(
                    session: todaySession,
                    seedItems: seedItems,
                    supportLanguageCode: supportLanguageCode,
                    streakCount: streakCount,
                    scheduledReviewCount: scheduledReviewCount,
                    dueReviewCount: dueReviewCount,
                    onReview: onReview
                ) {
                    refreshToday()
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    isShowingSettings = true
                } label: {
                    Image(systemName: "gearshape")
                }
                .accessibilityLabel(Text("settings.title"))
            }
        }
        .sheet(isPresented: $isShowingSettings) {
            NavigationStack {
                SettingsView()
            }
        }
    }

    private func refreshToday() {
        do {
            try loadSeedIfNeeded()
            let dayKey = dayKeyService.dayKey(for: Date())
            let sessions = try modelContext.fetch(FetchDescriptor<DailySession>())
            todaySession = sessions.first { $0.dayKey == dayKey }

            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            dueReviewCount = reviewScheduler.dueCount(from: progressRows, on: dayKey)
            scheduledReviewCount = todaySession?.scheduledReviewCount(from: progressRows) ?? 0
            streakCount = streakService.streakCount(from: sessions, currentDayKey: dayKey)
            if let todaySession {
                statusMessage = todaySession.targetItemCount < dailyTargetCount
                    ? selectionStatusMessage(for: .fewerThanTarget(
                        availableCount: todaySession.targetItemCount,
                        targetCount: dailyTargetCount
                    ))
                    : nil
            } else {
                statusMessage = selectionStatusMessage(
                    for: dailySelection(from: progressRows, on: dayKey).status
                )
            }
            writeWidgetSnapshot(dayKey: dayKey)
        } catch {
            statusMessage = String(localized: "today.load.error")
        }
    }

    private func startPractice() {
        do {
            try loadSeedIfNeeded()
            let dayKey = dayKeyService.dayKey(for: Date())
            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            dueReviewCount = reviewScheduler.dueCount(from: progressRows, on: dayKey)

            if let existingSession = try existingSession(for: dayKey), !existingSession.items.isEmpty {
                try markNewItemsFirstSeen(in: existingSession)
                try modelContext.save()
                todaySession = existingSession
                statusMessage = existingSession.targetItemCount < dailyTargetCount
                    ? selectionStatusMessage(for: .fewerThanTarget(
                        availableCount: existingSession.targetItemCount,
                        targetCount: dailyTargetCount
                    ))
                    : nil
                writeWidgetSnapshot(dayKey: dayKey)
                isShowingPractice = true
                return
            }

            let result = dailySelection(from: progressRows, on: dayKey)

            guard !result.itemIDs.isEmpty else {
                statusMessage = selectionStatusMessage(for: result.status)
                return
            }

            let session = try persistenceService.session(
                for: dayKey,
                itemIDs: result.itemIDs,
                reviewItemIDs: Set(result.reviewItemIDs),
                in: modelContext
            )
            try markNewItemsFirstSeen(in: session)

            try modelContext.save()
            todaySession = session
            writeWidgetSnapshot(dayKey: dayKey)
            statusMessage = selectionStatusMessage(for: result.status)
            isShowingPractice = true
        } catch {
            statusMessage = String(localized: "today.load.error")
        }
    }

    private func dailySelection(from progressRows: [WordProgress], on dayKey: String) -> DailySelectionResult {
        let dueReviewItemIDs = reviewScheduler
            .allDueItems(from: progressRows, on: dayKey)
            .map(\.itemID)

        return dailySelectionService.selectItems(
            from: seedItems,
            selectedLevel: preferencesStore.read().selectedLevel,
            contentLanguageCode: contentLanguageCode,
            supportLanguageCode: supportLanguageCode,
            firstSeenItemIDs: Set(progressRows.compactMap { $0.firstSeenAt == nil ? nil : $0.itemID }),
            dueReviewItemIDs: dueReviewItemIDs,
            targetCount: dailyTargetCount
        )
    }

    private func markNewItemsFirstSeen(in session: DailySession) throws {
        let seedByID = Dictionary(uniqueKeysWithValues: seedItems.map { ($0.id, $0) })

        for sessionItem in session.items where !sessionItem.isReviewFill {
            guard let seedItem = seedByID[sessionItem.itemID] else {
                continue
            }

            let progress = try persistenceService.wordProgress(
                for: seedItem.id,
                level: seedItem.level,
                in: modelContext
            )
            if progress.firstSeenAt == nil {
                progress.firstSeenAt = session.createdAt
            }
        }
    }

    private func selectionStatusMessage(for status: DailySelectionStatus) -> String? {
        switch status {
        case .full:
            return nil
        case .fewerThanTarget(availableCount: 0, targetCount: _):
            return String(localized: "today.seed.empty")
        case let .fewerThanTarget(availableCount, targetCount):
            return String.localizedStringWithFormat(
                String(localized: "today.seed.fewer"),
                availableCount,
                targetCount
            )
        }
    }

    private func existingSession(for dayKey: String) throws -> DailySession? {
        let descriptor = FetchDescriptor<DailySession>(
            predicate: #Predicate { $0.dayKey == dayKey }
        )
        return try modelContext.fetch(descriptor).first
    }

    private func loadSeedIfNeeded() throws {
        if seedItems.isEmpty {
            seedItems = try seedLoader.loadBundledSeed()
        }
    }

    private func writeWidgetSnapshot(dayKey: String) {
        guard let widgetSnapshotWriter else {
            return
        }

        let snapshot = WidgetSnapshot(
            dayKey: dayKey,
            progressCompleted: completedCount,
            progressTotal: totalCount,
            streakCount: streakCount,
            displayExpression: nextSeedItem.map {
                WidgetSnapshotExpression(
                    itemID: $0.id,
                    plainExpression: $0.plainExpression,
                    upgradedExpression: $0.upgradedExpression
                )
            },
            generatedAt: Date()
        )

        try? widgetSnapshotWriter.write(snapshot)
        WidgetCenter.shared.reloadTimelines(ofKind: WidgetSnapshotWriter.widgetKind)
    }
}

#Preview {
    NavigationStack {
        TodayView {}
    }
    .modelContainer(for: [
        WordProgress.self,
        DailySession.self,
        DailySessionItem.self,
        QuizResult.self
    ], inMemory: true)
}
