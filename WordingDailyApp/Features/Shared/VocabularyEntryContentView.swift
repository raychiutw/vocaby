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

    private var selectedSense: VocabularySense {
        item.senses.first { $0.id == senseID }!
    }

    private var additionalSenses: [VocabularySense] {
        guard showsAdditionalSenses else { return [] }
        return Array(item.senses.filter { $0.id != senseID }.prefix(2))
    }

    var body: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                Text(verbatim: item.upgradedExpression)
                    .font(.title2.bold())
                Text(verbatim: item.plainExpression)
                    .foregroundStyle(.secondary)
            }
            senseDetails(selectedSense)
        }

        if !additionalSenses.isEmpty {
            Section {
                DisclosureGroup("vocabulary.additionalSenses") {
                    ForEach(additionalSenses) { sense in
                        senseDetails(sense)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func senseDetails(_ sense: VocabularySense) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(partOfSpeechKey(sense.partOfSpeech))
                .font(.subheadline.weight(.semibold))

            Text("vocabulary.pronunciation")
                .font(.subheadline.weight(.semibold))

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
                    .frame(minHeight: 44)
                }
                .buttonStyle(.bordered)
                .accessibilityLabel(Text(verbatim: "\(item.upgradedExpression), \(region), /\(pronunciation.ipa)/"))
            }

            LabeledContent("vocabulary.meaning.english") {
                Text(verbatim: sense.meaning["en"] ?? "")
            }
            if supportLanguageCode != "en" {
                LabeledContent("vocabulary.meaning.support") {
                    Text(verbatim: localized(sense.meaning))
                }
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("vocabulary.example")
                    .font(.subheadline.weight(.semibold))
                Text(verbatim: sense.example.text)
                Text(verbatim: localized(sense.example.translation))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
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
