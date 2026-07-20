import SwiftData
import SwiftUI
import UIKit
import WidgetKit

struct TodayView: View {
    @Environment(\.modelContext) private var modelContext
    @State private var isShowingPractice = false
    @State private var isShowingExtraPractice = false
    @State private var todaySession: DailySession?
    @State private var seedItems: [VocabularySeedItem] = []
    @State private var dueReviewCount = 0
    @State private var scheduledReviewCount = 0
    @State private var streakCount = 0
    @State private var statusMessage: String?

    let onLearn: () -> Void
    let onReview: () -> Void
    let onPractice: () -> Void

    private let contentLanguageCode = "en"
    private let supportLanguageCode = "zh-Hant"
    private var dailyTargetCount: Int { preferencesStore.read().dailyGoal }
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

    private var progressFraction: Double {
        min(1, Double(completedCount) / Double(max(totalCount, 1)))
    }

    private var newLearnedCount: Int {
        orderedSessionItems.filter { !$0.isReviewFill && $0.answeredAt != nil }.count
    }

    private var reviewedCount: Int {
        orderedSessionItems.filter { $0.isReviewFill && $0.answeredAt != nil }.count
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

    private var reviewSummary: String {
        String.localizedStringWithFormat(
            String(localized: "today.review.estimatedTime.format"),
            dueReviewCount,
            max(1, dueReviewCount / 3 + 1)
        )
    }

    var body: some View {
        List {
            Section {
                HStack(spacing: 24) {
                    ZStack {
                        Circle()
                            .stroke(Color(.tertiarySystemFill), lineWidth: 14)
                        Circle()
                            .trim(from: 0, to: progressFraction)
                            .stroke(AppTheme.brandGradient, style: StrokeStyle(lineWidth: 14, lineCap: .round))
                            .rotationEffect(.degrees(-90))
                        VStack(spacing: 2) {
                            Text(progressText)
                                .font(.title2.bold().monospacedDigit())
                            Text("today.progress.accessibility")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .frame(width: 136, height: 136)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel(Text("today.progress.accessibility"))
                    .accessibilityValue(Text(progressText))

                    VStack(alignment: .leading, spacing: 12) {
                        Label("\(streakCount)", systemImage: "flame.fill")
                            .font(.headline.monospacedDigit())
                            .foregroundStyle(.orange)
                            .accessibilityLabel(Text("streak.label"))
                        if dueReviewCount > 0 {
                            Label("\(dueReviewCount)", systemImage: "clock.arrow.circlepath")
                                .font(.subheadline.bold().monospacedDigit())
                                .foregroundStyle(.orange)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(.orange.opacity(0.14), in: Capsule())
                                .accessibilityLabel(Text("review.title"))
                        } else {
                            Label("review.empty.title", systemImage: "checkmark.circle")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Button {
                    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                    onLearn()
                } label: {
                    Label(primaryButtonTitle, systemImage: "rectangle.stack.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(AppTheme.accent)
                .accessibilityIdentifier("today.start")

                HStack(spacing: 12) {
                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        onReview()
                    } label: {
                        Label("review.title", systemImage: "arrow.triangle.2.circlepath")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .disabled(dueReviewCount == 0)

                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        onPractice()
                    } label: {
                        Label("practice.tab.title", systemImage: "checkmark.circle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                }

                HStack {
                    dailySummaryValue(newLearnedCount, key: "progress.state.new")
                    dailySummaryValue(reviewedCount, key: "review.title")
                    dailySummaryValue(completedCount, key: "practice.tab.title")
                }
            }

            if let nextSeedItem {
                Section {
                CompactMetadataRow(
                    title: nextSeedItem.upgradedExpression,
                    subtitle: nextSeedItem.plainExpression,
                    systemImage: "text.quote",
                    tint: AppTheme.accent
                )
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
        .navigationDestination(isPresented: $isShowingExtraPractice) {
            PracticeCenterView(
                seedItems: seedItems,
                selectedLevel: preferencesStore.read().selectedLevel,
                supportLanguageCode: supportLanguageCode,
                startsImmediately: true,
                onUpdate: refreshToday
            )
        }
        .learningSettingsSheet()
    }

    private func dailySummaryValue(_ value: Int, key: LocalizedStringKey) -> some View {
        VStack(spacing: 4) {
            Text("\(value)").font(.headline).monospacedDigit()
            Text(key).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
    }

    private func refreshToday() {
        do {
            try loadSeedIfNeeded()
            let dayKey = dayKeyService.dayKey(for: Date())
            let sessions = try modelContext.fetch(FetchDescriptor<DailySession>())
            todaySession = sessions.first { $0.dayKey == dayKey }

            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            dueReviewCount = reviewScheduler.dueCount(from: progressRows, at: Date())
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
            dueReviewCount = reviewScheduler.dueCount(from: progressRows, at: Date())

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
            .allDueItems(from: progressRows, at: Date())
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
        TodayView(onLearn: {}, onReview: {}, onPractice: {})
    }
    .modelContainer(for: [
        WordProgress.self,
        DailySession.self,
        DailySessionItem.self,
        QuizResult.self,
        PracticeAttemptRecord.self
    ], inMemory: true)
}
