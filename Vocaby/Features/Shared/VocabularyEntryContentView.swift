import AVFAudio
import SwiftUI

enum PronunciationSpeaker {
    static func makeUtterance(
        expression: String,
        pronunciation: VocabularyPronunciation,
        availableVoices: [AVSpeechSynthesisVoice] = AVSpeechSynthesisVoice.speechVoices()
    ) -> AVSpeechUtterance {
        let utterance = AVSpeechUtterance(string: expression)
        let englishVoices = availableVoices.filter { $0.language.hasPrefix("en") }
        utterance.voice = englishVoices.first { $0.language == pronunciation.speechLocale }
            ?? englishVoices.first
            ?? AVSpeechSynthesisVoice(language: "en-US")
        return utterance
    }
}

struct VocabularyEntryContentView: View {
    let item: VocabularySeedItem
    let senseID: String
    let supportLanguageCode: String
    let showsAdditionalSenses: Bool
    let synthesizer: AVSpeechSynthesizer
    var showsExpression = true

    private var selectedSense: VocabularySense {
        item.senses.first { $0.id == senseID }!
    }

    private var additionalSenses: [VocabularySense] {
        guard showsAdditionalSenses else { return [] }
        return Array(item.senses.filter { $0.id != senseID }.prefix(2))
    }

    var body: some View {
        Section {
            VStack(alignment: .leading, spacing: 16) {
                if showsExpression {
                    Text(verbatim: item.upgradedExpression)
                        .font(.title2.bold())
                }

                pronunciationRow(for: selectedSense)

                Text(verbatim: localized(selectedSense.meaning))
                    .font(.title3.weight(.semibold))

                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(verbatim: item.plainExpression)
                        .foregroundStyle(.secondary)
                    Image(systemName: "arrow.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.tertiary)
                        .accessibilityHidden(true)
                    Text(verbatim: item.upgradedExpression)
                        .fontWeight(.semibold)
                }
                .accessibilityElement(children: .combine)

                VStack(alignment: .leading, spacing: 4) {
                    Text(verbatim: selectedSense.example.text)
                    Text(verbatim: localized(selectedSense.example.translation))
                        .foregroundStyle(.secondary)
                }

                DisclosureGroup("vocabulary.more") {
                    VStack(alignment: .leading, spacing: 16) {
                        Text(verbatim: selectedSense.meaning["en"] ?? "")

                        ForEach(additionalSenses) { sense in
                            Divider()
                            VStack(alignment: .leading, spacing: 6) {
                                Text(partOfSpeechKey(sense.partOfSpeech))
                                    .font(.subheadline.weight(.semibold))
                                Text(verbatim: localized(sense.meaning))
                                if supportLanguageCode != "en" {
                                    Text(verbatim: sense.meaning["en"] ?? "")
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func pronunciationRow(for sense: VocabularySense) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(partOfSpeechKey(sense.partOfSpeech))
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Spacer(minLength: 8)

            VStack(alignment: .trailing, spacing: 0) {
                ForEach(pronunciations(for: sense)) { pronunciation in
                    let region = regionLabel(pronunciation.region)
                    Button {
                        synthesizer.speak(PronunciationSpeaker.makeUtterance(
                            expression: item.upgradedExpression,
                            pronunciation: pronunciation
                        ))
                    } label: {
                        Label {
                            Text(verbatim: "\(region) /\(pronunciation.ipa)/")
                        } icon: {
                            Image(systemName: "speaker.wave.2")
                                .accessibilityHidden(true)
                        }
                        .font(.subheadline)
                        .frame(minHeight: 44)
                    }
                    .buttonStyle(.plain)
                    .minimumInteractiveSize()
                    .accessibilityLabel(Text(verbatim: "\(item.upgradedExpression), \(region), /\(pronunciation.ipa)/"))
                }
            }
        }
    }

    private func pronunciations(for sense: VocabularySense) -> [VocabularyPronunciation] {
        let ids = Set(sense.pronunciationIDs)
        return item.pronunciations.filter { ids.contains($0.id) }
    }

    private func localized(_ values: [String: String]) -> String {
        values[supportLanguageCode] ?? values["en"] ?? values.values.first ?? ""
    }

    private func regionLabel(_ region: String?) -> String {
        guard let region, region != "General" else {
            return String(localized: "vocabulary.region.general")
        }
        return region
    }

    private func partOfSpeechKey(_ value: VocabularyPartOfSpeech) -> LocalizedStringKey {
        switch value {
        case .noun: "vocabulary.pos.noun"
        case .verb: "vocabulary.pos.verb"
        case .adjective: "vocabulary.pos.adjective"
        case .adverb: "vocabulary.pos.adverb"
        case .preposition: "vocabulary.pos.preposition"
        case .conjunction: "vocabulary.pos.conjunction"
        case .interjection: "vocabulary.pos.interjection"
        case .pronoun: "vocabulary.pos.pronoun"
        case .determiner: "vocabulary.pos.determiner"
        case .phrase: "vocabulary.pos.phrase"
        }
    }
}
