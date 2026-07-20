import SwiftData
import SwiftUI

enum RootTab: Hashable {
    case home
    case learn
    case practice
    case progress
    case my
}

struct VocabyDeepLink: Equatable {
    let tab: RootTab
    let wordID: String?

    init(tab: RootTab, wordID: String? = nil) {
        self.tab = tab
        self.wordID = wordID
    }

    init?(url: URL) {
        guard url.scheme == "vocaby" else {
            return nil
        }

        let route = url.host ?? url.pathComponents.dropFirst().first

        switch route {
        case "today":
            tab = .home
            wordID = nil
        case "review":
            tab = .learn
            wordID = nil
        case "practice":
            tab = .practice
            wordID = nil
        case "progress":
            tab = .progress
            wordID = nil
        case "word":
            guard let id = url.pathComponents.dropFirst().first, !id.isEmpty else {
                return nil
            }
            tab = .my
            wordID = id
        default:
            return nil
        }
    }
}

struct RootTabView: View {
    @Query private var progressRows: [WordProgress]
    @State private var selectedTab = RootTab.home
    @State private var deepLinkedWordID: String?

    var body: some View {
        Group {
            if #available(iOS 26.0, *) {
                modernTabs
                    .tabBarMinimizeBehavior(.never)
            } else {
                legacyTabs
            }
        }
        .onOpenURL { url in
            route(url)
        }
        .onReceive(NotificationCenter.default.publisher(for: .vocabyInternalURL)) { notification in
            guard let url = notification.object as? URL else {
                return
            }

            route(url)
        }
    }

    @available(iOS 18.0, *)
    private var modernTabs: some View {
        TabView(selection: $selectedTab) {
            Tab("home.tab.title", systemImage: "house", value: RootTab.home) {
                homeRoot
            }

            Tab("learn.tab.title", systemImage: "rectangle.stack", value: RootTab.learn) {
                learnRoot
            }
            .badge(dueReviewCount)

            Tab("practice.tab.title", systemImage: "checkmark.circle", value: RootTab.practice) {
                practiceRoot
            }

            Tab("progress.tab.title", systemImage: "chart.xyaxis.line", value: RootTab.progress) {
                progressRoot
            }

            Tab("my.tab.title", systemImage: "person.crop.circle", value: RootTab.my) {
                myRoot
            }
        }
    }

    private var legacyTabs: some View {
        TabView(selection: $selectedTab) {
            homeRoot
            .tabItem {
                Label("home.tab.title", systemImage: "house")
            }
            .tag(RootTab.home)

            learnRoot
            .tabItem {
                Label("learn.tab.title", systemImage: "rectangle.stack")
            }
            .tag(RootTab.learn)
            .badge(dueReviewCount)

            practiceRoot
            .tabItem {
                Label("practice.tab.title", systemImage: "checkmark.circle")
            }
            .tag(RootTab.practice)

            progressRoot
            .tabItem {
                Label("progress.tab.title", systemImage: "chart.xyaxis.line")
            }
            .tag(RootTab.progress)

            myRoot
            .tabItem {
                Label("my.tab.title", systemImage: "person.crop.circle")
            }
            .tag(RootTab.my)
        }
    }

    private var homeRoot: some View {
        NavigationStack {
            TodayView {
                selectedTab = .learn
            }
        }
    }

    private var learnRoot: some View {
        NavigationStack {
            LearnView()
        }
    }

    private var practiceRoot: some View {
        NavigationStack {
            PracticeTabRoot()
        }
    }

    private var progressRoot: some View {
        NavigationStack {
            LearningProgressView()
        }
    }

    private var myRoot: some View {
        NavigationStack {
            LibraryView(deepLinkedItemID: $deepLinkedWordID)
        }
    }

    private var dueReviewCount: Int {
        ReviewScheduler().dueCount(from: progressRows, at: Date())
    }

    private func route(_ url: URL) {
        guard let deepLink = VocabyDeepLink(url: url) else {
            return
        }

        selectedTab = deepLink.tab
        deepLinkedWordID = deepLink.wordID
    }
}

private struct PracticeTabRoot: View {
    @State private var seedItems: [VocabularySeedItem] = []
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if !seedItems.isEmpty {
                PracticeCenterView(
                    seedItems: seedItems,
                    selectedLevel: UserPreferencesStore().read().selectedLevel,
                    supportLanguageCode: "zh-Hant"
                )
            } else if let errorMessage {
                ContentUnavailableView(
                    "practice.load.error.title",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
            } else {
                ProgressView()
            }
        }
        .task {
            do {
                seedItems = try SeedLoader().loadBundledSeed()
            } catch {
                errorMessage = String(localized: "practice.load.error")
            }
        }
    }
}

#Preview {
    RootTabView()
}
