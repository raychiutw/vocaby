import AVFoundation
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
    @State private var statusMessage: String?

    private let contentLanguageCode = "en"
    private let supportLanguageCode = "zh-Hant"
    private let dayKeyService = DayKeyService()
    private let dailySelectionService = DailySelectionService()
    private let persistenceService = ProgressPersistenceService()
    private let preferencesStore = UserPreferencesStore()
    private let reviewScheduler = ReviewScheduler()
    private let seedLoader = SeedLoader()
    private let widgetSnapshotWriter = WidgetSnapshotWriter.appGroupWriter()

    private var orderedSessionItems: [DailySessionItem] {
        (todaySession?.items ?? []).sorted { $0.position < $1.position }
    }

    private var completedCount: Int {
        orderedSessionItems.filter { $0.answeredAt != nil }.count
    }

    private var totalCount: Int {
        let itemCount = orderedSessionItems.count
        return itemCount > 0 ? itemCount : 10
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
                        Label(primaryButtonTitle, systemImage: completedCount == totalCount ? "checkmark.circle.fill" : "play.fill")
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
                TodayPracticeView(
                    session: todaySession,
                    seedItems: seedItems,
                    supportLanguageCode: supportLanguageCode
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
            let sessionDescriptor = FetchDescriptor<DailySession>(
                predicate: #Predicate { $0.dayKey == dayKey }
            )
            todaySession = try modelContext.fetch(sessionDescriptor).first

            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            dueReviewCount = reviewScheduler.dueItems(from: progressRows, on: dayKey, limit: 10).count
            writeWidgetSnapshot(dayKey: dayKey)
            statusMessage = nil
        } catch {
            statusMessage = String(localized: "today.load.error")
        }
    }

    private func startPractice() {
        do {
            try loadSeedIfNeeded()
            let dayKey = dayKeyService.dayKey(for: Date())

            if let existingSession = try existingSession(for: dayKey), !existingSession.items.isEmpty {
                todaySession = existingSession
                writeWidgetSnapshot(dayKey: dayKey)
                isShowingPractice = true
                return
            }

            let progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            let dueReviewItemIDs = reviewScheduler
                .dueItems(from: progressRows, on: dayKey, limit: 10)
                .map(\.itemID)
            let result = dailySelectionService.selectItems(
                from: seedItems,
                selectedLevel: preferencesStore.read().selectedLevel,
                contentLanguageCode: contentLanguageCode,
                supportLanguageCode: supportLanguageCode,
                seenItemIDs: Set(progressRows.map(\.itemID)),
                dueReviewItemIDs: dueReviewItemIDs
            )

            guard !result.itemIDs.isEmpty else {
                statusMessage = String(localized: "today.seed.empty")
                return
            }

            let session = try persistenceService.session(
                for: dayKey,
                itemIDs: result.itemIDs,
                targetItemCount: 10,
                in: modelContext
            )
            let seedByID = Dictionary(uniqueKeysWithValues: seedItems.map { ($0.id, $0) })

            for itemID in result.itemIDs {
                guard let item = seedByID[itemID] else {
                    continue
                }

                _ = try persistenceService.wordProgress(for: itemID, level: item.level, in: modelContext)
            }

            try modelContext.save()
            todaySession = session
            dueReviewCount = dueReviewItemIDs.count
            writeWidgetSnapshot(dayKey: dayKey)
            statusMessage = nil
            isShowingPractice = true
        } catch {
            statusMessage = String(localized: "today.load.error")
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
            streakCount: 0,
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

private struct TodayPracticeView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.modelContext) private var modelContext

    let session: DailySession
    let seedItems: [VocabularySeedItem]
    let supportLanguageCode: String
    let onUpdate: () -> Void

    @State private var selectedOptionIndex: Int?
    @State private var errorMessage: String?
    @State private var speechSynthesizer = AVSpeechSynthesizer()

    private let persistenceService = ProgressPersistenceService()
    private let reviewScheduler = ReviewScheduler()

    private var orderedSessionItems: [DailySessionItem] {
        session.items.sorted { $0.position < $1.position }
    }

    private var currentSessionItem: DailySessionItem? {
        orderedSessionItems.first { $0.answeredAt == nil }
    }

    private var currentIndex: Int {
        guard let currentSessionItem else {
            return orderedSessionItems.count
        }

        return (orderedSessionItems.firstIndex { $0 === currentSessionItem } ?? 0) + 1
    }

    private var currentSeedItem: VocabularySeedItem? {
        guard let currentSessionItem else {
            return nil
        }

        return seedItems.first { $0.id == currentSessionItem.itemID }
    }

    var body: some View {
        List {
            if let item = currentSeedItem, currentSessionItem != nil {
                Section {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            Text("\(currentIndex)/\(max(orderedSessionItems.count, 1))")
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
                    }
                }
            } else {
                Section {
                    Text("practice.completed")
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
        .navigationTitle("practice.title")
        .safeAreaInset(edge: .bottom) {
            if selectedOptionIndex != nil, currentSeedItem != nil {
                VStack(spacing: 0) {
                    Button {
                        persistAnswer()
                    } label: {
                        Text("practice.next")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .tint(AppTheme.accent)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(.regularMaterial)
            }
        }
    }

    @ViewBuilder
    private func answerIcon(for index: Int, correctOptionIndex: Int) -> some View {
        if selectedOptionIndex != nil && index == correctOptionIndex {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(Color("CorrectGreen"))
        } else if selectedOptionIndex == index {
            Image(systemName: "xmark.circle.fill")
                .foregroundStyle(Color("WrongRed"))
        }
    }

    private func answerTint(for index: Int, correctOptionIndex: Int) -> Color? {
        guard let selectedOptionIndex else {
            return nil
        }

        if index == correctOptionIndex {
            return Color("CorrectGreen")
        }

        return selectedOptionIndex == index ? Color("WrongRed") : nil
    }

    private func persistAnswer() {
        guard let currentSessionItem, let item = currentSeedItem, let selectedOptionIndex else {
            return
        }

        do {
            let now = Date()
            let wasCorrect = selectedOptionIndex == item.quiz.correctOptionIndex
            currentSessionItem.selectedOptionIndex = selectedOptionIndex
            currentSessionItem.wasCorrect = wasCorrect
            currentSessionItem.answeredAt = now

            let progress = try persistenceService.wordProgress(for: item.id, level: item.level, in: modelContext)
            reviewScheduler.applyAnswer(
                to: progress,
                wasCorrect: wasCorrect,
                answeredAt: now,
                context: .dailyPractice
            )
            _ = try persistenceService.quizResult(
                dayKey: session.dayKey,
                itemID: item.id,
                selectedOptionIndex: selectedOptionIndex,
                correctOptionIndex: item.quiz.correctOptionIndex,
                in: modelContext
            )

            if session.items.allSatisfy({ $0.answeredAt != nil }) {
                session.completedAt = now
            }

            try modelContext.save()
            self.selectedOptionIndex = nil
            errorMessage = nil
            onUpdate()
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
        TodayView()
    }
    .modelContainer(for: [
        WordProgress.self,
        DailySession.self,
        DailySessionItem.self,
        QuizResult.self
    ], inMemory: true)
}
