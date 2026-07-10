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

    var body: some View {
        List {
            Picker("library.scope.accessibility", selection: $selectedScope) {
                Text("library.scope.learned").tag(LibraryScope.learned)
                Text("library.scope.saved").tag(LibraryScope.saved)
            }
            .pickerStyle(.segmented)
            .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 12, trailing: 16))

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
                .font(.headline)
            Text(item.seedItem.plainExpression)
                .foregroundStyle(.secondary)
            Text(statusText)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }

    private var statusText: LocalizedStringKey {
        guard let progress = item.progress else {
            return "library.row.practiced"
        }

        if progress.masteredAt != nil {
            return "library.row.mastered"
        }

        if progress.isSaved {
            return "library.row.saved"
        }

        return "library.row.practiced"
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
            Section {
                VStack(alignment: .leading, spacing: 12) {
                    Text(item.seedItem.upgradedExpression)
                        .font(.title2.weight(.semibold))
                    Text(item.seedItem.plainExpression)
                        .foregroundStyle(.secondary)
                    Text(localized(item.seedItem.meaning))
                    Text(item.seedItem.example.text)
                        .foregroundStyle(.secondary)
                    Text(localized(item.seedItem.example.translation))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .padding(.vertical, 8)
            }

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

    private func localized(_ values: [String: String]) -> String {
        values[supportLanguageCode] ?? values.values.first ?? ""
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
        QuizResult.self
    ], inMemory: true)
}
