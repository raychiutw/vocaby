struct ReviewQueueService {
    func queuedItems(
        from seedItems: [VocabularySeedItem],
        dueProgressRows: [WordProgress],
        contentLanguageCode: String,
        supportLanguageCode: String
    ) -> [VocabularySeedItem] {
        let seedByID = Dictionary(uniqueKeysWithValues: seedItems.map { ($0.id, $0) })

        return dueProgressRows.compactMap { progress in
            guard let item = seedByID[progress.itemID],
                  item.contentLanguageCode == contentLanguageCode,
                  item.supportLanguageCodes.contains(supportLanguageCode) else {
                return nil
            }

            return item
        }
    }
}
