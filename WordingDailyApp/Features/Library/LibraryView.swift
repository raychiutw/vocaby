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

    private var emptyMessageKey: LocalizedStringKey {
        if !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "library.empty.search"
        }

        return selectedScope == .learned ? "library.empty.learned" : "library.empty.saved"
    }

    private var practicedItemCount: Int {
        progressRows.filter { $0.firstSeenAt != nil }.count
    }

    private var compactProgress: String {
        String.localizedStringWithFormat(
            String(localized: "library.compactProgress.format"),
            practicedItemCount,
            seedItems.count
        )
    }

    var body: some View {
        List {
            Section {
                HStack(spacing: 12) {
                    Image("LibraryCover")
                        .resizable()
                        .scaledToFill()
                        .frame(width: 56, height: 56)
                        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                    VStack(alignment: .leading, spacing: 4) {
                        Text("library.title")
                            .font(.headline)

                        Text(compactProgress)
                            .font(.subheadline.monospacedDigit())
                            .foregroundStyle(.secondary)
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
                    Text(emptyMessageKey)
                        .foregroundStyle(.secondary)
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
        .navigationTitle("library.title")
        .searchable(text: $query, prompt: Text("library.search.prompt"))
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

private struct LibraryRowView: View {
    let item: LibraryListItem

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(item.seedItem.upgradedExpression)
                .font(.body.weight(.semibold))
            Text("\(item.seedItem.plainExpression) · \(statusText)")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(.vertical, 6)
    }

    private var statusText: String {
        guard let progress = item.progress else {
            return String(localized: "library.row.practiced")
        }

        if progress.masteredAt != nil {
            return String(localized: "library.row.mastered")
        }

        if progress.isSaved {
            return String(localized: "library.row.saved")
        }

        return String(localized: "library.row.practiced")
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
    @State private var isRestoringSavedState = false
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
                synthesizer: speechSynthesizer
            )

            Section {
                Toggle(isOn: $isSaved) {
                    Label("library.detail.saved", systemImage: isSaved ? "bookmark.fill" : "bookmark")
                }
                .onChange(of: isSaved) { _, newValue in
                    guard !isRestoringSavedState else {
                        isRestoringSavedState = false
                        return
                    }
                    updateSavedState(newValue)
                }
            }

            Section("library.detail.review") {
                LabeledContent("library.detail.correct", value: "\(progress?.correctCount ?? 0)")
                LabeledContent("library.detail.wrong", value: "\(progress?.wrongCount ?? 0)")
                LabeledContent("library.detail.due", value: progress?.dueDayKey ?? String(localized: "library.detail.notScheduled"))
                if progress?.masteredAt != nil {
                    Label("library.detail.mastered", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(AppTheme.correctGreen)
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
            progress = currentProgress
            errorMessage = nil
            onUpdate()
        } catch {
            isRestoringSavedState = true
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
