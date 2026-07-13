import Foundation

enum DailySelectionStatus: Equatable {
    case full
    case fewerThanTarget(availableCount: Int, targetCount: Int)
}

struct DailySelectionResult: Equatable {
    let itemIDs: [String]
    let newItemIDs: [String]
    let reviewItemIDs: [String]
    let status: DailySelectionStatus
}

struct DailySelectionService {
    func selectItems(
        from seedItems: [VocabularySeedItem],
        selectedLevel: VocabularyLevel,
        contentLanguageCode: String,
        supportLanguageCode: String,
        firstSeenItemIDs: Set<String>,
        dueReviewItemIDs: [String],
        targetCount: Int = 10
    ) -> DailySelectionResult {
        let eligibleItems = seedItems
            .filter { item in
                item.level == selectedLevel &&
                    item.contentLanguageCode == contentLanguageCode &&
                    item.supportLanguageCodes.contains(supportLanguageCode)
            }
            .sorted { lhs, rhs in
                if lhs.sortOrder == rhs.sortOrder {
                    return lhs.id < rhs.id
                }
                return lhs.sortOrder < rhs.sortOrder
            }

        let eligibleIDs = Set(eligibleItems.map(\.id))
        let newItemIDs = eligibleItems
            .map(\.id)
            .filter { !firstSeenItemIDs.contains($0) }
            .prefix(targetCount)

        var selectedIDs = Array(newItemIDs)
        var reviewItemIDs: [String] = []
        var selectedIDSet = Set(selectedIDs)

        for itemID in dueReviewItemIDs where selectedIDs.count < targetCount {
            guard eligibleIDs.contains(itemID),
                  !selectedIDSet.contains(itemID) else {
                continue
            }

            selectedIDs.append(itemID)
            reviewItemIDs.append(itemID)
            selectedIDSet.insert(itemID)
        }

        let status: DailySelectionStatus = selectedIDs.count == targetCount
            ? .full
            : .fewerThanTarget(availableCount: selectedIDs.count, targetCount: targetCount)

        return DailySelectionResult(
            itemIDs: selectedIDs,
            newItemIDs: Array(newItemIDs),
            reviewItemIDs: reviewItemIDs,
            status: status
        )
    }
}
