import AVFAudio
import SwiftData
import SwiftUI

struct LibraryView: View {
    @Environment(\.modelContext) private var modelContext
    @Binding private var deepLinkedItemID: String?

    @State private var query = ""
    @State private var selectedScope = LibraryScope.learned
    @State private var seedItems: [VocabularySeedItem] = []
    @State private var progressRows: [WordProgress] = []
    @State private var quizResults: [QuizResult] = []
    @State private var statusMessage: String?
    @State private var selectedDetailItemID: String?

    private let contentLanguageCode = "en"
    private let supportLanguageCode = "zh-Hant"
    private let libraryService = LibraryService()
    private let seedLoader = SeedLoader()

    init(deepLinkedItemID: Binding<String?> = .constant(nil)) {
        _deepLinkedItemID = deepLinkedItemID
    }

    private var libraryItems: [LibraryListItem] {
        libraryService.items(
            from: seedItems,
            progressRows: progressRows,
            quizResults: quizResults,
            scope: selectedScope,
            query: query,
            contentLanguageCode: contentLanguageCode,
            supportLanguageCode: supportLanguageCode
        )
    }

    private var levelSummaries: [LibraryLevelSummary] {
        libraryService.levelSummaries(
            from: seedItems,
            quizResults: quizResults,
            contentLanguageCode: contentLanguageCode,
            supportLanguageCode: supportLanguageCode
        )
    }

    private var emptyMessageKey: LocalizedStringKey {
        if !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "library.empty.search"
        }

        return selectedScope == .learned ? "library.empty.learned" : "library.empty.saved"
    }

    private var hasSearchableContent: Bool {
        progressRows.contains { $0.firstSeenAt != nil || $0.isSaved }
    }

    var body: some View {
        Group {
            if hasSearchableContent {
                libraryList
                    .searchable(text: $query, prompt: Text("library.search.prompt"))
            } else {
                libraryList
            }
        }
        .navigationTitle("library.title")
        .navigationDestination(item: $selectedDetailItemID) { itemID in
            Group {
                if let item = detailItem(for: itemID) {
                    LibraryDetailView(
                        item: item,
                        supportLanguageCode: supportLanguageCode
                    ) {
                        refreshLibrary()
                    }
                } else {
                    Text("library.empty.search")
                }
            }
        }
        .task {
            refreshLibrary()
        }
        .onChange(of: deepLinkedItemID) { _, _ in
            refreshLibrary()
        }
        .learningSettingsSheet()
    }

    private var libraryList: some View {
        List {
            if !seedItems.isEmpty {
                Section("my.progress.title") {
                    ForEach(levelSummaries) { summary in
                        MyLevelProgressRow(summary: summary)
                    }
                }
            }

            Picker("library.scope.accessibility", selection: $selectedScope) {
                Text("library.scope.learned").tag(LibraryScope.learned)
                Text("library.scope.saved").tag(LibraryScope.saved)
            }
            .pickerStyle(.segmented)
            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))

            if libraryItems.isEmpty {
                Section {
                    ContentUnavailableView(emptyMessageKey, systemImage: "books.vertical")
                }
            } else {
                Section {
                    ForEach(libraryItems) { item in
                        NavigationLink {
                            LibraryDetailView(
                                item: item,
                                supportLanguageCode: supportLanguageCode
                            ) {
                                refreshLibrary()
                            }
                        } label: {
                            LibraryRowView(item: item)
                        }
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
    }

    private func refreshLibrary() {
        do {
            try loadSeedIfNeeded()
            progressRows = try modelContext.fetch(FetchDescriptor<WordProgress>())
            quizResults = try modelContext.fetch(FetchDescriptor<QuizResult>())
            statusMessage = nil
            openDeepLinkedItemIfNeeded()
        } catch {
            statusMessage = String(localized: "library.load.error")
        }
    }

    private func loadSeedIfNeeded() throws {
        if seedItems.isEmpty {
            seedItems = try seedLoader.loadBundledSeed()
        }
    }

    private func openDeepLinkedItemIfNeeded() {
        guard let itemID = deepLinkedItemID else {
            return
        }

        deepLinkedItemID = nil
        selectedDetailItemID = detailItem(for: itemID)?.id
    }

    private func detailItem(for itemID: String) -> LibraryListItem? {
        guard let seedItem = seedItems.first(where: { $0.id == itemID }) else {
            return nil
        }

        return LibraryListItem(
            seedItem: seedItem,
            progress: progressRows.first { $0.itemID == itemID }
        )
    }
}

private struct MyLevelProgressRow: View {
    let summary: LibraryLevelSummary

    private var levelTitleKey: LocalizedStringKey {
        switch summary.level {
        case .basic: "settings.level.basic"
        case .intermediate: "settings.level.intermediate"
        case .advanced: "settings.level.advanced"
        }
    }

    private var countText: String {
        String.localizedStringWithFormat(
            String(localized: "my.progress.count.format"),
            summary.learnedCount,
            summary.totalCount
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(levelTitleKey)
                    .font(.body.weight(.semibold))
                Spacer(minLength: 12)
                Text(countText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }

            ProgressView(value: summary.progress)
                .tint(Color("Accent"))
                .accessibilityHidden(true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(Text(levelTitleKey))
        .accessibilityValue(Text(countText))
    }
}

private struct LibraryRowView: View {
    let item: LibraryListItem

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(item.seedItem.upgradedExpression)
                    .font(.body.weight(.semibold))
                Text(item.seedItem.plainExpression)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer(minLength: 8)

            if item.progress?.masteredAt != nil {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(AppTheme.correctGreen)
                    .accessibilityLabel(Text("library.detail.mastered"))
            }
        }
        .padding(.vertical, 6)
    }
}

private struct LibraryDetailView: View {
    @Environment(\.modelContext) private var modelContext

    let item: LibraryListItem
    let supportLanguageCode: String
    let onUpdate: () -> Void

    @State private var isSaved: Bool
    @State private var progress: WordProgress?
    @State private var errorMessage: String?
    @State private var speechSynthesizer = AVSpeechSynthesizer()

    private let persistenceService = ProgressPersistenceService()

    init(
        item: LibraryListItem,
        supportLanguageCode: String,
        onUpdate: @escaping () -> Void
    ) {
        self.item = item
        self.supportLanguageCode = supportLanguageCode
        self.onUpdate = onUpdate
        _isSaved = State(initialValue: item.progress?.isSaved ?? false)
        _progress = State(initialValue: item.progress)
    }

    var body: some View {
        List {
            VocabularyEntryContentView(
                item: item.seedItem,
                senseID: item.seedItem.primarySenseID,
                supportLanguageCode: supportLanguageCode,
                showsAdditionalSenses: true,
                synthesizer: speechSynthesizer,
                showsExpression: false
            )

            if let progress {
                Section {
                    Text(reviewSummary(for: progress))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    if progress.masteredAt != nil {
                        Label("library.detail.mastered", systemImage: "checkmark.seal.fill")
                            .foregroundStyle(AppTheme.correctGreen)
                    }
                }
            }

            if let errorMessage {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(AppTheme.wrongRed)
                }
            }
        }
        .navigationTitle(item.seedItem.upgradedExpression)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    updateSavedState(!isSaved)
                } label: {
                    Image(systemName: isSaved ? "bookmark.fill" : "bookmark")
                }
                .accessibilityLabel(Text(isSaved ? "library.detail.removeSaved" : "library.detail.save"))
            }
        }
    }

    private func reviewSummary(for progress: WordProgress) -> String {
        String.localizedStringWithFormat(
            String(localized: "library.detail.summary.format"),
            progress.correctCount,
            progress.wrongCount
        )
    }

    private func updateSavedState(_ newValue: Bool) {
        do {
            let currentProgress = try persistenceService.wordProgress(
                for: item.seedItem.id,
                level: item.seedItem.level,
                in: modelContext
            )
            currentProgress.isSaved = newValue
            currentProgress.updatedAt = Date()
            try modelContext.save()
            isSaved = newValue
            progress = currentProgress
            errorMessage = nil
            onUpdate()
        } catch {
            isSaved = progress?.isSaved ?? false
            errorMessage = String(localized: "library.save.error")
        }
    }
}

#Preview {
    NavigationStack {
        LibraryView()
    }
    .modelContainer(for: [
        WordProgress.self,
        DailySession.self,
        DailySessionItem.self,
        QuizResult.self,
        PracticeAttemptRecord.self
    ], inMemory: true)
}
