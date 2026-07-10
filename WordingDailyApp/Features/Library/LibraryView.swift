import SwiftUI

struct LibraryView: View {
    @State private var query = ""
    @State private var selectedScope = LibraryScope.learned

    var body: some View {
        List {
            Picker("library.scope.accessibility", selection: $selectedScope) {
                Text("library.scope.learned").tag(LibraryScope.learned)
                Text("library.scope.saved").tag(LibraryScope.saved)
            }
            .pickerStyle(.segmented)
            .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 12, trailing: 16))

            Section {
                Text("library.empty.message")
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("library.title")
        .searchable(text: $query, prompt: Text("library.search.prompt"))
    }
}

private enum LibraryScope {
    case learned
    case saved
}

#Preview {
    NavigationStack {
        LibraryView()
    }
}
