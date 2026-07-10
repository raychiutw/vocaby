import SwiftUI

struct RootTabView: View {
    var body: some View {
        TabView {
            NavigationStack {
                TodayView()
            }
            .tabItem {
                Label("today.tab.title", systemImage: "sun.max")
            }

            NavigationStack {
                ReviewView()
            }
            .tabItem {
                Label("review.tab.title", systemImage: "arrow.triangle.2.circlepath")
            }

            NavigationStack {
                LibraryView()
            }
            .tabItem {
                Label("library.tab.title", systemImage: "books.vertical")
            }
        }
    }
}

#Preview {
    RootTabView()
}
