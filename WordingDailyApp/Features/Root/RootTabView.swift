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
        TabView(selection: $selectedTab) {
            NavigationStack {
                TodayView {
                    selectedTab = .review
                }
            }
            .tabItem {
                Label("today.tab.title", systemImage: "sun.max")
            }
            .tag(RootTab.today)

            NavigationStack {
                ReviewView()
            }
            .tabItem {
                Label("review.tab.title", systemImage: "arrow.triangle.2.circlepath")
            }
            .tag(RootTab.review)

            NavigationStack {
                LibraryView(deepLinkedItemID: $deepLinkedWordID)
            }
            .tabItem {
                Label("library.tab.title", systemImage: "books.vertical")
            }
            .tag(RootTab.library)
        }
        .onOpenURL { url in
            route(url)
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
