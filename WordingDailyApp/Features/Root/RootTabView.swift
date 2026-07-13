import SwiftUI

enum RootTab: Hashable {
    case today
    case review
    case library
}

struct WordingDailyDeepLink: Equatable {
    let tab: RootTab
    let wordID: String?

    init(tab: RootTab, wordID: String? = nil) {
        self.tab = tab
        self.wordID = wordID
    }

    init?(url: URL) {
        guard url.scheme == "wordingdaily" else {
            return nil
        }

        let route = url.host ?? url.pathComponents.dropFirst().first

        switch route {
        case "today":
            tab = .today
            wordID = nil
        case "review":
            tab = .review
            wordID = nil
        case "word":
            guard let id = url.pathComponents.dropFirst().first, !id.isEmpty else {
                return nil
            }
            tab = .library
            wordID = id
        default:
            return nil
        }
    }
}

struct RootTabView: View {
    @State private var selectedTab = RootTab.today
    @State private var deepLinkedWordID: String?

    var body: some View {
        Group {
            if #available(iOS 26.0, *) {
                modernTabs
                    .tabBarMinimizeBehavior(.onScrollDown)
            } else {
                legacyTabs
            }
        }
        .onOpenURL { url in
            route(url)
        }
        .onReceive(NotificationCenter.default.publisher(for: .wordingDailyInternalURL)) { notification in
            guard let url = notification.object as? URL else {
                return
            }

            route(url)
        }
    }

    @available(iOS 18.0, *)
    private var modernTabs: some View {
        TabView(selection: $selectedTab) {
            Tab("today.tab.title", systemImage: "sun.max", value: RootTab.today) {
                todayRoot
            }

            Tab("review.tab.title", systemImage: "arrow.triangle.2.circlepath", value: RootTab.review) {
                reviewRoot
            }

            Tab("library.tab.title", systemImage: "books.vertical", value: RootTab.library) {
                libraryRoot
            }
        }
    }

    private var legacyTabs: some View {
        TabView(selection: $selectedTab) {
            todayRoot
            .tabItem {
                Label("today.tab.title", systemImage: "sun.max")
            }
            .tag(RootTab.today)

            reviewRoot
            .tabItem {
                Label("review.tab.title", systemImage: "arrow.triangle.2.circlepath")
            }
            .tag(RootTab.review)

            libraryRoot
            .tabItem {
                Label("library.tab.title", systemImage: "books.vertical")
            }
            .tag(RootTab.library)
        }
    }

    private var todayRoot: some View {
        NavigationStack {
            TodayView {
                selectedTab = .review
            }
        }
    }

    private var reviewRoot: some View {
        NavigationStack {
            ReviewView()
        }
    }

    private var libraryRoot: some View {
        NavigationStack {
            LibraryView(deepLinkedItemID: $deepLinkedWordID)
        }
    }

    private func route(_ url: URL) {
        guard let deepLink = WordingDailyDeepLink(url: url) else {
            return
        }

        selectedTab = deepLink.tab
        deepLinkedWordID = deepLink.wordID
    }
}

#Preview {
    RootTabView()
}
