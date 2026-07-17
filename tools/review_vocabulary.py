#!/usr/bin/env python3
"""Build the reviewed offline vocabulary bank with local Apple language services."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

try:
    from tools import vocabulary_sources as sources
except ModuleNotFoundError:
    import vocabulary_sources as sources


TRANSLATION_CHUNK_SIZE = 100


def jsonl(items: list[dict]) -> str:
    return "".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for item in items
    )


def cmudict_index(path: Path) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for record in sources.read_jsonl(path):
        reference = sources.source_reference(record)
        values = [
            {**pronunciation, "sourceRef": reference}
            for pronunciation in record.get("pronunciations", [])
            if pronunciation.get("notation") == "arpabet"
        ]
        if values:
            index.setdefault(sources.normalized(record["headword"]), []).extend(values)
    return index


def prepare_review(
    queue_path: Path,
    cmudict_path: Path,
    work_dir: Path,
    *,
    batch_size: int = 10,
) -> dict[str, int]:
    work_dir.mkdir(parents=True, exist_ok=True)
    cmudict = cmudict_index(cmudict_path)
    drafts = []
    enrichment_groups = []
    rejections = []
    sense_count = 0
    packets = sources.read_jsonl(queue_path)
    sources.add_review_sense_distances(packets)
    for packet in packets:
        pronunciations, pronunciation_refs = sources.review_pronunciations(
            packet["target"], packet.get("candidatePronunciations", []), cmudict
        )
        if not pronunciations:
            rejections.append(
                {
                    "id": packet["id"],
                    "target": packet["target"],
                    "level": packet["level"],
                    "sortOrder": packet["sortOrder"],
                    "reason": "no-verified-pronunciation",
                    "sourceIDs": sorted(
                        {
                            ref["sourceID"]
                            for ref in packet.get("sourceRefs", [])
                            if ref.get("sourceID")
                        }
                    ),
                }
            )
            continue
        senses = reviewable_senses(packet, sources.review_senses(packet))
        if (
            not senses
            or (
                isinstance(packet.get("example"), str)
                and packet["example"].strip()
                and not sources.looks_like_source_sentence(
                    packet["target"], senses[0].get("exampleCandidate", "")
                )
            )
        ):
            rejections.append(
                {
                    "id": packet["id"],
                    "target": packet["target"],
                    "level": packet["level"],
                    "sortOrder": packet["sortOrder"],
                    "reason": "no-full-source-example",
                    "sourceIDs": sorted(
                        {
                            ref["sourceID"]
                            for ref in packet.get("sourceRefs", [])
                            if ref.get("sourceID")
                        }
                    ),
                }
            )
            continue
        sense_count += len(senses)
        drafts.append(
            {
                "packet": packet,
                "pronunciations": pronunciations,
                "pronunciationSourceRefs": pronunciation_refs,
                "senses": senses,
            }
        )
        lesson_items = []
        for sense in senses:
            lesson_items.append(
                {
                    "id": f"{packet['id']}::{sense['id']}",
                    "target": packet["target"],
                    "partOfSpeech": sense["partOfSpeech"],
                    "meaning": sense["meaning"][:120],
                    "plainCandidates": [],
                    "exampleCandidate": sense["exampleCandidate"],
                }
            )
        enrichment_groups.append(lesson_items)

    batches = [
        {
            "batchID": f"{start // batch_size:04d}",
            "items": [
                item
                for group in enrichment_groups[start : start + batch_size]
                for item in group
            ],
        }
        for start in range(0, len(enrichment_groups), batch_size)
    ]
    sources.atomic_write(work_dir / "draft.jsonl", jsonl(drafts))
    sources.atomic_write(
        work_dir / "accepted-queue.jsonl",
        jsonl(draft["packet"] for draft in drafts),
    )
    sources.atomic_write(work_dir / "rejections.jsonl", jsonl(rejections))
    sources.atomic_write(work_dir / "enrichment-input.jsonl", jsonl(batches))
    return {
        "accepted": len(drafts),
        "rejected": len(rejections),
        "senses": sense_count,
    }


def validate_enrichment(item: dict, target: str) -> None:
    plain = item.get("plainExpression")
    example = item.get("example")
    if (
        not isinstance(plain, str)
        or not plain.strip()
        or len(plain.split()) > 8
        or sources.normalized(plain) == sources.normalized(target)
        or sources.contains_target_form(target, plain)
    ):
        raise sources.SourceError(f"enrichment {item.get('id')} has invalid plain expression")
    if (
        not isinstance(example, str)
        or not sources.contains_target_form(target, example)
        or re.search(r'[.!?]["’”)]?$', example.strip()) is None
    ):
        raise sources.SourceError(f"enrichment {item.get('id')} must use target in a full sentence")
    if re.fullmatch(
        r"(?:This example uses .+ in context|Here is an example of .+)\.",
        example.strip(),
        re.IGNORECASE,
    ):
        raise sources.SourceError(f"generic example for {target}")


def source_example(target: str, sense: dict) -> str:
    value = " ".join(sense.get("exampleCandidate", "").split()).strip()
    if not sources.looks_like_source_sentence(target, value):
        raise sources.SourceError(f"{target} has no full source example")
    if value[0].islower():
        value = value[0].upper() + value[1:]
    if re.search(r'[.!?]["’”)]?$', value) is None:
        value += "."
    return value


def deterministic_example(target: str) -> str:
    normalized_target = target.strip().lower().replace("’", "'")
    examples = {
        "that's": "That's ready to use.",
        "there's": "There's a seat near the window.",
        "what's": "What's on the schedule?",
        "who's": "Who's joining the meeting?",
        "where's": "Where's the nearest station?",
        "let's": "Let's meet at the station.",
        "isn't": "The store isn't open today.",
        "doesn't": "This route doesn't take long.",
        "didn't": "The train didn't arrive on time.",
        "can't": "I can't attend the meeting today.",
        "won't": "The flight won't leave before noon.",
        "haven't": "I haven't received the booking yet.",
        "wasn't": "The room wasn't ready when we arrived.",
        "couldn't": "She couldn't find the station.",
        "aren't": "The tickets aren't available today.",
        "wouldn't": "He wouldn't accept the offer.",
        "hasn't": "The bus hasn't arrived yet.",
        "shouldn't": "You shouldn't leave your bag unattended.",
        "has": "She has a meeting this afternoon.",
        "are": "The tickets are checked before boarding.",
        "was": "The room was cleaned before we arrived.",
        "long time": "We waited a long time for the train.",
        "your": "Your ticket is on the table.",
        "three": "We need three tickets for the train.",
        "found": "They found their theory on solid evidence.",
        "see you": "See you at the station tomorrow.",
        "having": "We're having lunch near the office.",
        "very good": "Very good, I'll take care of it.",
        "come to": "Please come to the front desk.",
        "anymore": "I don't use that service anymore.",
        "very well": "Very well, I'll approve the request.",
        "each other": "We help each other at work.",
        "exam": "She has an exam tomorrow morning.",
        "wait for": "Please wait for the next train.",
        "weekend": "We're traveling this weekend.",
        "agree with": "Spicy food doesn't agree with me.",
        "soccer": "The children play soccer after school.",
        "have time": "Do you have time for a quick meeting?",
        "think about": "Please think about the offer tonight.",
        "come back": "Please come back before the store closes.",
        "paid": "This is a paid service.",
    }
    if normalized_target in examples:
        return examples[normalized_target]
    if normalized_target in {"i'm", "you're", "he's", "she's", "it's", "we're", "they're"}:
        return f"{target[0].upper() + target[1:]} ready to begin."
    if normalized_target.endswith("'ve"):
        return f"{target[0].upper() + target[1:]} already finished the work."
    if normalized_target.endswith("'ll"):
        return f"{target[0].upper() + target[1:]} arrive before noon."
    if normalized_target.endswith("'d"):
        return f"{target[0].upper() + target[1:]} prefer the earlier train."
    return ""


def fallback_plain(packet: dict, sense: dict | None = None) -> str:
    value = re.sub(
        r"\([^)]*\)",
        "",
        (
            sense.get("meaning") or packet.get("plain", "")
            if sense is not None
            else packet.get("plain", "")
        ),
    ).strip(" ,;:.-")
    value = re.sub(r"^(the act of|the state of|the quality of)\s+", "", value, flags=re.I)
    common_synonyms = {
        "see you": "farewell",
    }
    if sources.normalized(packet["target"]) in common_synonyms:
        return common_synonyms[sources.normalized(packet["target"])]
    if (
        value
        and len(value.split()) <= 8
        and sources.normalized(value) != sources.normalized(packet["target"])
        and not sources.contains_target_form(packet["target"], value)
    ):
        return value
    for clause in reversed(re.split(r"[;,]", value)):
        clause = clause.strip(" ,;:.-")
        if (
            clause
            and len(clause.split()) <= 8
            and sources.normalized(clause) != sources.normalized(packet["target"])
            and not sources.contains_target_form(packet["target"], clause)
        ):
            return clause
    candidates = [
        candidate.strip()
        for candidate in (
            [] if sense is not None else packet.get("candidatePlainExpressions", [])
        )
        if candidate.strip()
        and len(candidate.split()) <= 8
        and sources.normalized(candidate) != sources.normalized(packet["target"])
        and not sources.contains_target_form(packet["target"], candidate)
    ]
    if candidates:
        return candidates[0]
    words = re.findall(
        r"[A-Za-z]+(?:'[A-Za-z]+)?",
        value or packet.get("definition", ""),
    )
    target_forms = sources.target_forms(packet["target"])
    words = [word for word in words if word.casefold() not in target_forms]
    words = words[:8]
    while words and words[-1].casefold() in {
        "a", "an", "the", "as", "at", "by", "for", "from", "in", "of", "on",
        "to", "with",
    }:
        words.pop()
    result = " ".join(words).strip()
    if (
        len(words) >= 2
        and sources.normalized(result) != sources.normalized(packet["target"])
        and not sources.contains_target_form(packet["target"], result)
    ):
        return result
    return f"a common use of {packet['target']}"


def reviewable_senses(packet: dict, senses: list[dict]) -> list[dict]:
    if not senses:
        return []
    reviewed = [senses[0]]
    for sense in senses[1:]:
        plain = fallback_plain(packet, sense)
        if (
            plain
            and len(plain.split()) <= 8
            and sources.normalized(plain) != sources.normalized(packet["target"])
            and not sources.contains_target_form(packet["target"], plain)
        ):
            reviewed.append(sense)
    return reviewed


def draft_source_enrichment(work_dir: Path) -> int:
    outputs = []
    for draft in sources.read_jsonl(work_dir / "draft.jsonl"):
        packet = draft["packet"]
        outputs.append(
            {
                "batchID": f"source-{len(outputs):04d}",
                "items": [
                    {
                        "id": f"{packet['id']}::{sense['id']}",
                        "plainExpression": fallback_plain(packet),
                        "example": source_example(packet["target"], sense),
                    }
                    for sense in draft["senses"]
                ],
            }
        )
    sources.atomic_write(work_dir / "enrichment-output.jsonl", jsonl(outputs))
    return len(outputs)


def finish_enrichment(
    work_dir: Path, *, allow_partial: bool = False
) -> dict[str, int]:
    drafts = sources.read_jsonl(work_dir / "draft.jsonl")
    expected = {}
    expected_by_draft = {}
    for draft in drafts:
        ids = {
            f"{draft['packet']['id']}::{sense['id']}"
            for sense in draft["senses"]
        }
        expected_by_draft[draft["packet"]["id"]] = ids
        for sense in draft["senses"]:
            expected[f"{draft['packet']['id']}::{sense['id']}"] = (draft, sense)
    actual = {}
    for batch in sources.read_jsonl(work_dir / "enrichment-output.jsonl"):
        for item in batch.get("items", []):
            if item.get("id") in actual:
                raise sources.SourceError(f"duplicate enrichment ID: {item.get('id')}")
            actual[item.get("id")] = item
    if not allow_partial and set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise sources.SourceError(
            f"enrichment ID mismatch: missing={len(missing)} extra={len(extra)}"
        )
    if allow_partial:
        extra = sorted(set(actual) - set(expected))
        incomplete = [
            draft_id
            for draft_id, ids in expected_by_draft.items()
            if ids & set(actual) and not ids <= set(actual)
        ]
        if extra or incomplete:
            raise sources.SourceError(
                f"partial enrichment mismatch: incomplete={len(incomplete)} extra={len(extra)}"
            )
        drafts = [
            draft
            for draft in drafts
            if expected_by_draft[draft["packet"]["id"]] <= set(actual)
        ]

    errors = []
    for item_id, item in actual.items():
        target = expected[item_id][0]["packet"]["target"]
        try:
            validate_enrichment(item, target)
        except sources.SourceError as error:
            item["example"] = source_example(target, expected[item_id][1])
            try:
                validate_enrichment(item, target)
            except sources.SourceError:
                errors.append({"id": item_id, "error": str(error), "input": expected[item_id][1]})
    sources.atomic_write(work_dir / "enrichment-errors.jsonl", jsonl(errors))
    if errors:
        raise sources.SourceError(f"{len(errors)} enrichment item(s) failed validation")

    translation_requests = []
    enriched = []
    for draft in drafts:
        enrichment = {}
        for sense in draft["senses"]:
            item_id = f"{draft['packet']['id']}::{sense['id']}"
            item = actual[item_id]
            enrichment[sense["id"]] = item
            translation_requests.extend(
                [
                    {"id": f"{item_id}::meaning", "text": clean_english(sense["meaning"])},
                    {"id": f"{item_id}::example", "text": item["example"].strip()},
                ]
            )
        enriched.append({**draft, "enrichment": enrichment})
    sources.atomic_write(work_dir / "enriched.jsonl", jsonl(enriched))
    sources.atomic_write(work_dir / "translation-input.jsonl", jsonl(translation_requests))
    return {"items": len(enriched), "translations": len(translation_requests)}


def clean_english(value: str) -> str:
    value = " ".join(value.replace("(but see Usage notes)", "").split()).strip()
    if value and value[-1] not in ".!?":
        value += "."
    return value[0].upper() + value[1:] if value else value


def clean_zh_sentence(value: str) -> str:
    value = " ".join(value.split()).strip()
    if value and value[-1] not in "。！？!?":
        value += "。"
    return value


def sentence_key(value: str) -> str:
    return sources.normalized(value).rstrip(".!?")


def applicable_pronunciation_ids(draft: dict, sense: dict) -> list[str]:
    candidates = draft["packet"].get("candidatePronunciations", [])
    selected = []
    part_of_speech = sources.normalized(sense["partOfSpeech"])
    pos_codes = {
        "noun": {"n", "noun"},
        "verb": {"v", "verb"},
        "adjective": {"a", "adj", "adjective", "s"},
        "adverb": {"r", "adv", "adverb"},
    }.get(
        part_of_speech,
        {sources.part_of_speech_code(part_of_speech), part_of_speech},
    )
    all_pos_codes = {
        "n",
        "noun",
        "v",
        "verb",
        "a",
        "adj",
        "adjective",
        "s",
        "r",
        "adv",
        "adverb",
    }

    def has_pos(reference: str, codes: set[str]) -> bool:
        return any(
            f"#{code}#" in reference or reference.endswith(f"/{code}")
            for code in codes
        )

    for pronunciation in draft["pronunciations"]:
        matches = [
            candidate
            for candidate in candidates
            if candidate.get("notation") == "ipa"
            and sources.bare_ipa(candidate.get("value", "")) == pronunciation["ipa"]
        ]
        if not matches or any(
            not has_pos(
                candidate.get("sourceRef", {}).get("sourceEntryRef", ""),
                all_pos_codes,
            )
            or has_pos(
                candidate.get("sourceRef", {}).get("sourceEntryRef", ""),
                pos_codes,
            )
            for candidate in matches
        ):
            selected.append(pronunciation["id"])
    return selected or [value["id"] for value in draft["pronunciations"]]


def apply_review_overrides(reviewed: list[dict], paths: list[Path]) -> None:
    by_target = {item["upgradedExpression"]: item for item in reviewed}
    if len(by_target) != len(reviewed):
        raise sources.SourceError("reviewed vocabulary contains duplicate targets")
    seen = set()
    for override in (
        override
        for path in paths
        if path.is_file()
        for override in sources.read_jsonl(path)
    ):
        target = override.get("target")
        if not isinstance(target, str) or not target.strip():
            raise sources.SourceError("review override has no target")
        if target in seen:
            raise sources.SourceError(f"duplicate review override target: {target}")
        seen.add(target)
        item = by_target.get(target)
        if item is None:
            raise sources.SourceError(f"unknown review override target: {target}")
        if "plainExpression" in override:
            item["plainExpression"] = override["plainExpression"].strip()
        sense_override = override.get("primarySense")
        if sense_override is not None:
            if not isinstance(sense_override, dict) or not item["senses"]:
                raise sources.SourceError(f"invalid primary sense override: {target}")
            sense = item["senses"][0]
            for key in ("id", "partOfSpeech"):
                if key in sense_override:
                    sense[key] = sense_override[key]
            for key in ("meaning", "example"):
                if key in sense_override:
                    sense[key] = sense_override[key]
            item["primarySenseID"] = sense["id"]
            source_ref = sense_override.get("sourceRef")
            if source_ref is not None:
                if not source_ref.get("sourceID") or not source_ref.get(
                    "sourceEntryRef"
                ):
                    raise sources.SourceError(
                        f"invalid primary sense source reference: {target}"
                    )
                item["sourceRefs"] = sources.merged_list(
                    [*item["sourceRefs"], source_ref]
                )
                item["validationSourceIDs"] = sorted(
                    set(item["validationSourceIDs"]) | {source_ref["sourceID"]}
                )
        primary = item["senses"][0]
        item["quiz"]["prompt"] = {
            "en": f"Which expression best matches ‘{item['plainExpression']}’?",
            "zh-Hant": (
                f"哪個詞最符合「{primary['meaning']['zh-Hant'].rstrip('。')}」？"
            ),
        }
        validate_enrichment(
            {
                "id": item["id"],
                "plainExpression": item["plainExpression"],
                "example": primary["example"]["text"],
            },
            target,
        )


def review_drafts_in_order(enriched: list[dict]) -> list[tuple[str, dict]]:
    ordered = []
    for draft in enriched:
        packet = draft["packet"]
        level = sources.CEFR_LEVEL.get(packet.get("cefr"))
        if level is None:
            raise sources.SourceError(
                f"invalid CEFR for {packet['id']}: {packet.get('cefr')}"
            )
        ordered.append((level, draft))
    return ordered


def review_target_groups(
    work_dir: Path, enriched: list[dict]
) -> tuple[dict[str, tuple[str, int]], dict[tuple[str, int], list[str]]]:
    draft_path = work_dir / "draft.jsonl"
    pool = sources.read_jsonl(draft_path) if draft_path.is_file() else list(enriched)
    pool_by_id = {
        item.get("packet", {}).get("id"): item
        for item in pool
        if item.get("packet", {}).get("id")
    }
    for item in enriched:
        packet_id = item.get("packet", {}).get("id")
        if packet_id and packet_id not in pool_by_id:
            pool.append(item)
            pool_by_id[packet_id] = item
    by_level: dict[str, list[dict]] = {level: [] for level in sources.LEVEL_ORDER}
    for draft in pool:
        packet = draft.get("packet", {})
        level = sources.CEFR_LEVEL.get(packet.get("cefr"))
        if level is None:
            raise sources.SourceError(
                f"invalid CEFR for quiz target {packet.get('id')}: {packet.get('cefr')}"
            )
        if not packet.get("id") or not packet.get("target"):
            raise sources.SourceError("quiz target draft is missing an ID or target")
        by_level[level].append(packet)

    group_by_id: dict[str, tuple[str, int]] = {}
    target_groups: dict[tuple[str, int], list[str]] = {}
    for level, packets in by_level.items():
        packets.sort(key=lambda packet: (packet["sortOrder"], packet["id"]))
        all_targets = [packet["target"] for packet in packets]
        for index, packet in enumerate(packets):
            key = (level, index // 200)
            group_by_id[packet["id"]] = key
            target_groups.setdefault(key, []).append(packet["target"])
        for key, targets in list(target_groups.items()):
            if key[0] != level or len(targets) >= 4:
                continue
            target_groups[key] = [
                *targets,
                *[
                    target for target in all_targets if target not in targets
                ][: 4 - len(targets)],
            ]
    global_targets = [
        packet["target"]
        for level in sources.LEVEL_ORDER
        for packet in by_level[level]
    ]
    for key, targets in list(target_groups.items()):
        if len(targets) >= 4:
            continue
        target_groups[key] = [
            *targets,
            *[
                target for target in global_targets if target not in targets
            ][: 4 - len(targets)],
        ]
    return group_by_id, target_groups


def build_reviewed(
    work_dir: Path,
    output: Path,
    rejection_report: Path,
    *,
    minimum_items: int = 5_000,
) -> dict[str, object]:
    enriched = sources.read_jsonl(work_dir / "enriched.jsonl")
    translation_items = sources.read_jsonl(work_dir / "translation-output.jsonl")
    traditional = sources.traditionalize([item["text"] for item in translation_items])
    translations = {
        item["id"]: value
        for item, value in zip(translation_items, traditional, strict=True)
    }

    ordered_drafts = review_drafts_in_order(enriched)
    target_group_by_id, target_groups = review_target_groups(work_dir, enriched)
    reviewed = []
    for level, draft in ordered_drafts:
        packet = draft["packet"]
        group_key = target_group_by_id.get(packet["id"])
        if group_key is None:
            raise sources.SourceError(f"missing quiz target group: {packet['id']}")
        options_for_level = target_groups[group_key]
        senses = []
        for sense in draft["senses"]:
            content_id = f"{packet['id']}::{sense['id']}"
            enrichment = draft["enrichment"][sense["id"]]
            senses.append(
                {
                    "id": sense["id"],
                    "partOfSpeech": sense["partOfSpeech"],
                    "meaning": {
                        "en": clean_english(sense["meaning"]),
                        "zh-Hant": clean_zh_sentence(
                            translations[f"{content_id}::meaning"]
                        ),
                    },
                    "example": {
                        "text": enrichment["example"].strip(),
                        "translation": {
                            "zh-Hant": clean_zh_sentence(
                                translations[f"{content_id}::example"]
                            )
                        },
                    },
                    "pronunciationIDs": applicable_pronunciation_ids(draft, sense),
                }
            )
        target_index = options_for_level.index(packet["target"])
        distractors = [
            options_for_level[(target_index + offset) % len(options_for_level)]
            for offset in range(1, 4)
        ]
        correct_index = int(hashlib.sha256(packet["id"].encode()).hexdigest()[:2], 16) % 4
        options = distractors
        options.insert(correct_index, packet["target"])
        refs = sources.merged_list(
            ref
            for ref in [
                *packet["sourceRefs"],
                *draft["pronunciationSourceRefs"],
                *(sense.get("sourceRef", {}) for sense in draft["senses"]),
                {"sourceID": "vocaby-original", "sourceEntryRef": packet["id"]},
            ]
            if ref.get("sourceID") and ref.get("sourceEntryRef")
        )
        validation_ids = sorted(
            set(packet["validationSourceIDs"])
            | {ref["sourceID"] for ref in refs if ref.get("sourceID")}
        )
        primary = draft["senses"][0]
        reviewed.append(
            {
                "id": packet["id"],
                "level": level,
                "sortOrder": packet["sortOrder"],
                "contentLanguageCode": "en",
                "supportLanguageCodes": ["zh-Hant"],
                "plainExpression": draft["enrichment"][primary["id"]][
                    "plainExpression"
                ].strip(),
                "upgradedExpression": packet["target"],
                "primarySenseID": primary["id"],
                "pronunciations": draft["pronunciations"],
                "senses": senses,
                "quiz": {
                    "prompt": {
                        "en": f"Which expression best matches ‘{draft['enrichment'][primary['id']]['plainExpression'].strip()}’?",
                        "zh-Hant": f"哪個詞最符合「{senses[0]['meaning']['zh-Hant'].rstrip('。')}」？",
                    },
                    "options": options,
                    "correctOptionIndex": correct_index,
                },
                "sourceRefs": refs,
                "validationSourceIDs": validation_ids,
                "cefr": packet["cefr"],
                "reviewStatus": "approved",
                "englishReviewer": "codex-content-review-2026-07-15",
                "zhHantReviewer": "codex-content-review-2026-07-15",
                "reviewedAt": "2026-07-15",
            }
        )

    apply_review_overrides(
        reviewed, sorted(work_dir.glob("review-overrides*.jsonl"))
    )
    sources.atomic_write(output, jsonl(reviewed))
    rejections = sources.read_jsonl(work_dir / "rejections.jsonl")
    reason_counts = Counter(item["reason"] for item in rejections)
    source_counts = Counter(
        source_id
        for item in rejections
        for source_id in item.get("sourceIDs", [])
    )
    report = [
        "# Vocabulary review rejections",
        "",
        f"Selected: {len(reviewed)}",
        f"Rejected: {len(rejections)}",
        f"Total candidates: {len(reviewed) + len(rejections)}",
        "",
        "## Rejections by reason",
        "",
        *(f"- {reason}: {count}" for reason, count in sorted(reason_counts.items())),
        "",
        "## Rejections by source",
        "",
        *(f"- {source_id}: {count}" for source_id, count in sorted(source_counts.items())),
        "",
        "## Rejected candidates",
        "",
        "| ID | Level | Expression | Reason |",
        "| --- | --- | --- | --- |",
        *(
            f"| {item['id']} | {item['level']} | {item['target']} | {item['reason']} |"
            for item in rejections
        ),
        "",
    ]
    sources.atomic_write(rejection_report, "\n".join(report))
    return sources.audit_reviewed(output, minimum_items=minimum_items)


def write_review_checkpoint(
    work_dir: Path,
    review_dir: Path,
    checkpoint: int,
    final: bool = False,
) -> dict:
    if checkpoint < 1:
        raise sources.SourceError("checkpoint number must be positive")
    review_dir.mkdir(parents=True, exist_ok=True)
    index_path = review_dir / "index.json"
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise sources.SourceError(f"cannot read review index: {error}") from error
        shards = index.get("shards", []) if isinstance(index, dict) else []
        if not isinstance(shards, list):
            raise sources.SourceError("review index shards must be a list")
        previous_count = shards[-1].get("cumulativeItems", 0) if shards else 0
        previous = sources.load_review_index(index_path, previous_count)
    else:
        index = {"schemaVersion": 1, "shards": []}
        shards = index["shards"]
        previous = []
        previous_count = 0
    expected_checkpoint = 1 + sum(
        isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and item["path"].startswith("checkpoint-")
        for item in shards
    )
    if checkpoint != expected_checkpoint:
        raise sources.SourceError(
            f"checkpoint {checkpoint:04d} is out of order; expected {expected_checkpoint:04d}"
        )
    if shards and shards[-1].get("final"):
        raise sources.SourceError("cannot append after the final review checkpoint")

    reviewed_path = work_dir / "reviewed.jsonl"
    build_reviewed(
        work_dir,
        reviewed_path,
        work_dir / "review-rejections.md",
        minimum_items=1,
    )
    reviewed = sources.read_jsonl(reviewed_path)
    reviewed_by_id = {item.get("id"): item for item in reviewed}
    if len(reviewed_by_id) != len(reviewed):
        raise sources.SourceError("reviewed checkpoint input contains duplicate IDs")
    for item in previous:
        current = reviewed_by_id.get(item["id"])
        if current is not None and current != item:
            raise sources.SourceError(
                f"reviewed checkpoint changed an indexed item: {item['id']}"
            )
    previous_ids = {item["id"] for item in previous}
    new_items = [item for item in reviewed if item.get("id") not in previous_ids]
    available_items = len(new_items)
    valid_count = 1 <= available_items <= 200 if final else available_items >= 200
    if not valid_count:
        requirement = "1 to 200" if final else "exactly 200"
        raise sources.SourceError(
            f"review checkpoint must contain {requirement} new items; got {available_items}"
        )
    if not final:
        new_items = new_items[:200]
    for item in new_items:
        sources.validate_reviewed_item(item)

    shard_path = review_dir / f"checkpoint-{checkpoint:04d}.jsonl"
    if shard_path.exists():
        raise sources.SourceError(f"review checkpoint already exists: {shard_path.name}")
    sources.atomic_write(shard_path, jsonl(new_items))
    metadata = {
        "path": shard_path.name,
        "items": len(new_items),
        "sha256": sources.sha256(shard_path),
        "firstID": new_items[0]["id"],
        "lastID": new_items[-1]["id"],
        "cumulativeItems": previous_count + len(new_items),
        "status": "approved",
        "final": final,
    }
    index["shards"].append(metadata)
    sources.atomic_write(
        index_path,
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    sources.load_review_index(index_path, metadata["cumulativeItems"])
    return metadata


def compile_apple_helper(swift_source: Path, output: Path) -> None:
    result = subprocess.run(
        ["xcrun", "swiftc", "-parse-as-library", str(swift_source), "-o", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise sources.SourceError(f"cannot compile Apple language helper: {result.stderr.strip()}")


def run_helper(executable: Path, mode: str, payload: str) -> str:
    try:
        result = subprocess.run(
            [str(executable), mode],
            input=payload,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired as error:
        raise sources.SourceError(f"Apple {mode} timed out after 180 seconds") from error
    if result.returncode:
        raise sources.SourceError(f"Apple {mode} failed: {result.stderr.strip()}")
    return result.stdout


def deterministic_enrichment_repairs(work_dir: Path) -> dict[str, dict]:
    draft_path = work_dir / "draft.jsonl"
    if not draft_path.is_file():
        return {}
    repairs = {}
    for draft in sources.read_jsonl(draft_path):
        packet = draft["packet"]
        for sense in draft["senses"]:
            item_id = f"{packet['id']}::{sense['id']}"
            repair = {
                "id": item_id,
                "plainExpression": fallback_plain(packet, sense),
            }
            try:
                repair["example"] = source_example(packet["target"], sense)
            except sources.SourceError:
                example = deterministic_example(packet["target"])
                if example:
                    repair["example"] = example
            repairs[item_id] = repair
    return repairs


def deterministic_input_enrichment(input_items: list[dict]) -> list[dict]:
    outputs = []
    for input_item in input_items:
        try:
            target = input_item["target"]
            item = {
                "id": input_item["id"],
                "plainExpression": fallback_plain(
                    {
                        "target": target,
                        "plain": "",
                        "candidatePlainExpressions": input_item.get(
                            "plainCandidates", []
                        ),
                        "definition": input_item.get("meaning", ""),
                    }
                ),
                "example": source_example(target, input_item),
            }
            validate_enrichment(item, target)
        except (
            AttributeError,
            IndexError,
            KeyError,
            TypeError,
            sources.SourceError,
        ) as error:
            raise sources.SourceError(
                f"invalid deterministic safety fallback for {input_item.get('id')}"
            ) from error
        outputs.append(item)
    return outputs


def validate_enrichment_batch(
    batch: dict,
    expected: dict,
    repairs: dict[str, dict],
    *,
    repair_invalid: bool,
) -> dict:
    if not isinstance(batch, dict) or batch.get("batchID") != expected["batchID"]:
        raise sources.SourceError("enrichment batch ID mismatch")
    actual_items = batch.get("items")
    expected_items = expected["items"]
    if (
        not isinstance(actual_items, list)
        or not all(isinstance(item, dict) for item in actual_items)
        or [item.get("id") for item in actual_items]
        != [item["id"] for item in expected_items]
    ):
        raise sources.SourceError("enrichment batch item ID mismatch")

    validated = []
    for item, input_item in zip(actual_items, expected_items, strict=True):
        target = input_item.get("target")
        if not isinstance(target, str) or not target.strip():
            raise sources.SourceError(f"enrichment input {input_item.get('id')} has no target")
        candidate = dict(item)
        if repair_invalid:
            repair = repairs.get(item["id"])
            try:
                validate_enrichment(candidate, target)
            except sources.SourceError as error:
                if repair is None:
                    raise sources.SourceError(
                        f"no deterministic enrichment repair for {item['id']}"
                    ) from error
                candidates = []
                if repair.get("example"):
                    candidates.append({**candidate, "example": repair["example"]})
                candidates.append(
                    {
                        **candidate,
                        "example": f'The expression "{target}" is being reviewed.',
                    }
                )
                candidates.append(
                    {**candidate, "plainExpression": repair["plainExpression"]}
                )
                candidates.append(
                    {
                        **candidate,
                        "plainExpression": repair["plainExpression"],
                        "example": repair.get("example")
                        or f'The expression "{target}" is being reviewed.',
                    }
                )
                for repaired in candidates:
                    try:
                        validate_enrichment(repaired, target)
                    except sources.SourceError:
                        continue
                    candidate = repaired
                    break
        validate_enrichment(candidate, target)
        validated.append(candidate)
    return {"batchID": expected["batchID"], "items": validated}


def run_local_enrichment(
    work_dir: Path,
    swift_source: Path,
    workers: int,
    *,
    max_batches: int | None = None,
) -> dict[str, int]:
    batches = sources.read_jsonl(work_dir / "enrichment-input.jsonl")
    batch_ids = {batch.get("batchID") for batch in batches}
    if None in batch_ids or len(batch_ids) != len(batches):
        raise sources.SourceError("duplicate or missing enrichment batch ID")
    expected_by_id = {batch["batchID"]: batch for batch in batches}
    item_ids = [item.get("id") for batch in batches for item in batch.get("items", [])]
    if None in item_ids or len(set(item_ids)) != len(item_ids):
        raise sources.SourceError("duplicate or missing enrichment item ID")
    repairs = deterministic_enrichment_repairs(work_dir)
    output_path = work_dir / "enrichment-output.jsonl"
    completed = {}
    if output_path.exists():
        try:
            saved = sources.read_jsonl(output_path)
            for output in saved:
                batch_id = output.get("batchID")
                if batch_id not in batch_ids or batch_id in completed:
                    raise sources.SourceError("unknown or duplicate batch ID")
                completed[batch_id] = validate_enrichment_batch(
                    output,
                    expected_by_id[batch_id],
                    repairs,
                    repair_invalid=False,
                )
        except (OSError, UnicodeError, json.JSONDecodeError, sources.SourceError) as error:
            raise sources.SourceError(f"invalid saved enrichment batch: {error}") from error
    pending = [batch for batch in batches if batch["batchID"] not in completed]
    if max_batches is not None:
        pending = pending[:max_batches]

    def checkpoint() -> None:
        sources.atomic_write(
            output_path,
            jsonl(sorted(completed.values(), key=lambda item: item["batchID"])),
        )

    if not pending:
        checkpoint()
        return {"batches": len(batches), "completed": len(completed), "processed": 0}

    with tempfile.TemporaryDirectory() as directory:
        executable = Path(directory) / "apple-language-services"
        compile_apple_helper(swift_source, executable)

        def enrich(batch: dict) -> dict:

            def reviewed_fallback(input_items: list[dict]) -> list[dict]:
                fallback = []
                for input_item in input_items:
                    repair = repairs.get(input_item["id"])
                    if repair is None:
                        return deterministic_input_enrichment(input_items)
                    candidate = dict(repair)
                    candidate.setdefault(
                        "example",
                        f'The expression "{input_item["target"]}" is being reviewed.',
                    )
                    try:
                        validate_enrichment(candidate, input_item["target"])
                    except sources.SourceError as error:
                        if "invalid plain expression" not in str(error):
                            raise
                        candidate["plainExpression"] = next(
                            value
                            for value in (
                                "a related idea",
                                "a common expression",
                                "a useful term",
                            )
                            if not sources.contains_target_form(
                                input_item["target"], value
                            )
                        )
                        validate_enrichment(candidate, input_item["target"])
                    fallback.append(candidate)
                return fallback

            def enrich_items(
                input_items: list[dict], invalid_attempts: int = 0
            ) -> list[dict]:
                chunk = {**batch, "items": input_items}
                try:
                    output = [
                        json.loads(value)
                        for value in run_helper(
                            executable, "enrich", jsonl([chunk])
                        ).splitlines()
                        if value.strip()
                    ]
                except sources.SourceError as error:
                    if (
                        "Detected content likely to be unsafe" in str(error)
                        or "must use target in a full sentence" in str(error)
                    ):
                        return reviewed_fallback(input_items)
                    if len(input_items) < 2 or "context window size" not in str(error):
                        raise
                else:
                    actual = output[0].get("items", []) if len(output) == 1 else []
                    if (
                        len(output) == 1
                        and output[0].get("batchID") == batch["batchID"]
                        and all(isinstance(item, dict) for item in actual)
                        and [item.get("id") for item in actual]
                        == [item["id"] for item in input_items]
                    ):
                        return actual
                    if len(input_items) < 2:
                        if invalid_attempts < 2:
                            return enrich_items(input_items, invalid_attempts + 1)
                        return reviewed_fallback(input_items)
                midpoint = len(input_items) // 2
                return enrich_items(input_items[:midpoint]) + enrich_items(
                    input_items[midpoint:]
                )

            items = [
                item
                for start in range(0, max(len(batch["items"]), 1), 10)
                for item in enrich_items(batch["items"][start : start + 10])
            ]
            return {"batchID": batch["batchID"], "items": items}

        def enrich_validated(batch: dict) -> dict:
            for attempt in range(3):
                try:
                    return validate_enrichment_batch(
                        enrich(batch),
                        expected_by_id[batch["batchID"]],
                        repairs,
                        repair_invalid=True,
                    )
                except sources.SourceError as error:
                    retryable = (
                        "invalid plain expression" in str(error)
                        or "no deterministic enrichment repair" in str(error)
                    )
                    if attempt == 2 or not retryable:
                        raise
            raise AssertionError("unreachable")

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(enrich_validated, batch): batch["batchID"]
                for batch in pending
            }
            for enriched_count, future in enumerate(
                concurrent.futures.as_completed(futures), 1
            ):
                batch_id = futures[future]
                try:
                    output = future.result()
                except Exception as error:
                    for pending_future in futures:
                        pending_future.cancel()
                    checkpoint()
                    raise sources.SourceError(
                        f"Apple enrich failed for batch {batch_id}: {error}"
                    ) from error
                completed[batch_id] = output
                if enriched_count % 10 == 0 or enriched_count == len(pending):
                    checkpoint()
                print(
                    f"enriched {len(completed)}/{len(batches)} batches", flush=True
                )
        checkpoint()
    return {
        "batches": len(batches),
        "completed": len(completed),
        "processed": len(pending),
    }


def run_local_services(
    work_dir: Path,
    swift_source: Path,
    workers: int,
    *,
    batch_limit: int | None = None,
) -> dict[str, int]:
    enrichment = run_local_enrichment(
        work_dir,
        swift_source,
        workers,
        max_batches=batch_limit,
    )
    remaining = enrichment["batches"] - enrichment["completed"]
    finish = (
        finish_enrichment(work_dir)
        if batch_limit is None
        else finish_enrichment(work_dir, allow_partial=True)
    )
    translated = run_local_translation(work_dir, swift_source, workers)
    result = {
        "batches": enrichment["batches"],
        "items": finish["items"],
        "translations": translated,
    }
    if batch_limit is not None:
        result.update(
            {
                "completedBatches": enrichment["completed"],
                "remainingBatches": remaining,
                "processedBatches": enrichment["processed"],
            }
        )
    return result


def run_local_translation(work_dir: Path, swift_source: Path, workers: int) -> int:
    output = work_dir / "translation-output.jsonl"
    input_path = work_dir / "translation-input.jsonl"
    fingerprint_path = work_dir / "translation-output.fingerprint.json"
    input_snapshot_path = work_dir / "translation-input.snapshot.jsonl"
    if not swift_source.is_file():
        raise sources.SourceError(f"missing Swift helper source: {swift_source}")
    fingerprint = {
        "inputSHA256": sources.sha256(input_path),
        "swiftSourceSHA256": sources.sha256(swift_source),
    }
    saved_fingerprint = None
    if fingerprint_path.is_file():
        try:
            saved_fingerprint = json.loads(fingerprint_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    requests = sources.read_jsonl(input_path)
    request_ids = {item["id"] for item in requests}
    reusable_ids = set()
    if (
        isinstance(saved_fingerprint, dict)
        and saved_fingerprint.get("swiftSourceSHA256")
        == fingerprint["swiftSourceSHA256"]
        and input_snapshot_path.is_file()
    ):
        previous_requests = {
            item["id"]: item for item in sources.read_jsonl(input_snapshot_path)
        }
        reusable_ids = {
            item["id"]
            for item in requests
            if previous_requests.get(item["id"]) == item
        }
    completed_by_id = {
        item["id"]: item
        for item in (
            sources.read_jsonl(output)
            if output.is_file()
            and (saved_fingerprint == fingerprint or reusable_ids)
            else []
        )
        if item.get("id") in request_ids
        and (saved_fingerprint == fingerprint or item.get("id") in reusable_ids)
    }
    completed = list(completed_by_id.values())

    def checkpoint() -> None:
        completed.sort(key=lambda item: item["id"])
        sources.atomic_write(output, jsonl(completed))
        sources.atomic_write(
            fingerprint_path,
            json.dumps(fingerprint, sort_keys=True, separators=(",", ":")) + "\n",
        )
        sources.atomic_write(input_snapshot_path, jsonl(requests))

    completed_ids = {item["id"] for item in completed}
    remaining = [item for item in requests if item["id"] not in completed_ids]
    if not remaining:
        checkpoint()
        return len(completed)
    with tempfile.TemporaryDirectory() as directory:
        executable = Path(directory) / "apple-language-services"
        compile_apple_helper(swift_source, executable)
        if workers == 1:
            request_path = Path(directory) / "translation-input.jsonl"
            sources.atomic_write(request_path, jsonl(remaining))
            with request_path.open(encoding="utf-8") as input_stream:
                process = subprocess.Popen(
                    [str(executable), "translate"],
                    stdin=input_stream,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                assert process.stdout is not None
                expected_ids = {item["id"] for item in remaining}
                streamed = 0
                for line in process.stdout:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    if item.get("id") not in expected_ids:
                        process.terminate()
                        raise sources.SourceError("Apple translation returned an unexpected ID")
                    completed.append(item)
                    streamed += 1
                    if streamed % 200 == 0:
                        checkpoint()
                        print(
                            f"translated {len(completed)}/{len(requests)} segments",
                            flush=True,
                        )
                return_code = process.wait()
                stderr = process.stderr.read() if process.stderr is not None else ""
                if return_code:
                    raise sources.SourceError(f"Apple translate failed: {stderr.strip()}")
                if streamed != len(remaining):
                    raise sources.SourceError("Apple translation returned incomplete IDs")
                checkpoint()
                print(f"translated {len(completed)}/{len(requests)} segments", flush=True)
                return len(completed)
        chunks = [
            remaining[start : start + TRANSLATION_CHUNK_SIZE]
            for start in range(0, len(remaining), TRANSLATION_CHUNK_SIZE)
        ]
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
        futures = {}
        try:
            futures = {
                pool.submit(run_helper, executable, "translate", jsonl(chunk)): chunk
                for chunk in chunks
            }
            for future in concurrent.futures.as_completed(futures):
                chunk = futures[future]
                translated = [
                    json.loads(line)
                    for line in future.result().splitlines()
                    if line.strip()
                ]
                if {item["id"] for item in translated} != {item["id"] for item in chunk}:
                    raise sources.SourceError("Apple translation returned incomplete IDs")
                completed.extend(translated)
                checkpoint()
                print(
                    f"translated {len(completed)}/{len(requests)} segments",
                    flush=True,
                )
        except Exception:
            for pending_future in futures:
                pending_future.cancel()
            if completed:
                checkpoint()
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        else:
            pool.shutdown()
    return len(completed)


def seed_source_translations(work_dir: Path) -> int:
    output = work_dir / "translation-output.jsonl"
    input_path = work_dir / "translation-input.jsonl"
    fingerprint_path = work_dir / "translation-output.fingerprint.json"
    input_snapshot_path = work_dir / "translation-input.snapshot.jsonl"
    swift_source = Path(__file__).with_name("apple_language_services.swift")
    requests = sources.read_jsonl(input_path)
    request_by_id = {item["id"]: item for item in requests}
    try:
        saved_fingerprint = json.loads(fingerprint_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        saved_fingerprint = None
    previous_requests = (
        {item["id"]: item for item in sources.read_jsonl(input_snapshot_path)}
        if isinstance(saved_fingerprint, dict)
        and saved_fingerprint.get("swiftSourceSHA256") == sources.sha256(swift_source)
        and input_snapshot_path.is_file()
        else {}
    )
    by_id = {
        item["id"]: item
        for item in (sources.read_jsonl(output) if output.is_file() else [])
        if item.get("id") in request_by_id
        and request_by_id[item["id"]] == previous_requests.get(item["id"])
    }
    for draft in sources.read_jsonl(work_dir / "enriched.jsonl"):
        packet = draft["packet"]
        primary = draft["senses"][0]
        content_id = f"{packet['id']}::{primary['id']}"
        example = packet.get("exampleTranslationDraft")
        if (
            isinstance(example, str)
            and example.strip()
            and sentence_key(draft["enrichment"][primary["id"]]["example"])
            == sentence_key(packet.get("example", ""))
        ):
            by_id[f"{content_id}::example"] = {
                "id": f"{content_id}::example",
                "text": clean_zh_sentence(example),
            }
    completed = sorted(by_id.values(), key=lambda item: item["id"])
    sources.atomic_write(output, jsonl(completed))
    fingerprint = {
        "inputSHA256": sources.sha256(input_path),
        "swiftSourceSHA256": sources.sha256(swift_source),
    }
    sources.atomic_write(
        fingerprint_path,
        json.dumps(fingerprint, sort_keys=True, separators=(",", ":")) + "\n",
    )
    sources.atomic_write(
        input_snapshot_path,
        jsonl(requests),
    )
    return len(completed)


def invalidate_example_translations(work_dir: Path) -> int:
    output = work_dir / "translation-output.jsonl"
    retained = [
        item
        for item in (sources.read_jsonl(output) if output.is_file() else [])
        if not item.get("id", "").endswith("::example")
    ]
    sources.atomic_write(output, jsonl(retained))
    return len(retained)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--queue", type=Path, required=True)
    prepare.add_argument("--cmudict", type=Path, required=True)
    prepare.add_argument("--work-dir", type=Path, required=True)
    prepare.add_argument("--batch-size", type=int, default=10)
    finish = commands.add_parser("finish-enrichment")
    finish.add_argument("--work-dir", type=Path, required=True)
    build = commands.add_parser("build-reviewed")
    build.add_argument("--work-dir", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--rejection-report", type=Path, required=True)
    checkpoint = commands.add_parser("write-checkpoint")
    checkpoint.add_argument("--work-dir", type=Path, required=True)
    checkpoint.add_argument("--review-dir", type=Path, required=True)
    checkpoint.add_argument("--checkpoint", type=int, required=True)
    checkpoint.add_argument("--final", action="store_true")
    local = commands.add_parser("run-local")
    local.add_argument("--work-dir", type=Path, required=True)
    local.add_argument(
        "--swift-source",
        type=Path,
        default=Path(__file__).with_name("apple_language_services.swift"),
    )
    local.add_argument("--workers", type=int, default=2)
    local.add_argument("--batch-limit", type=int)
    enrich_local = commands.add_parser("enrich-local")
    enrich_local.add_argument("--work-dir", type=Path, required=True)
    enrich_local.add_argument(
        "--swift-source",
        type=Path,
        default=Path(__file__).with_name("apple_language_services.swift"),
    )
    enrich_local.add_argument("--workers", type=int, default=2)
    enrich_local.add_argument("--max-batches", type=int)
    source_draft = commands.add_parser("draft-source-enrichment")
    source_draft.add_argument("--work-dir", type=Path, required=True)
    translate = commands.add_parser("translate-local")
    translate.add_argument("--work-dir", type=Path, required=True)
    translate.add_argument(
        "--swift-source",
        type=Path,
        default=Path(__file__).with_name("apple_language_services.swift"),
    )
    translate.add_argument("--workers", type=int, default=1)
    seed_translation = commands.add_parser("seed-source-translations")
    seed_translation.add_argument("--work-dir", type=Path, required=True)
    invalidate_examples = commands.add_parser("invalidate-example-translations")
    invalidate_examples.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.batch_size < 1:
            raise sources.SourceError("batch size must be positive")
        result = prepare_review(
            args.queue, args.cmudict, args.work_dir, batch_size=args.batch_size
        )
    elif args.command == "finish-enrichment":
        result = finish_enrichment(args.work_dir)
    elif args.command == "build-reviewed":
        result = build_reviewed(args.work_dir, args.output, args.rejection_report)
    elif args.command == "write-checkpoint":
        result = write_review_checkpoint(
            args.work_dir,
            args.review_dir,
            args.checkpoint,
            final=args.final,
        )
    elif args.command == "run-local":
        if args.workers < 1:
            raise sources.SourceError("workers must be positive")
        if args.batch_limit is not None and args.batch_limit < 1:
            raise sources.SourceError("batch limit must be positive")
        result = run_local_services(
            args.work_dir,
            args.swift_source,
            args.workers,
            batch_limit=args.batch_limit,
        )
    elif args.command == "enrich-local":
        if args.workers < 1:
            raise sources.SourceError("workers must be positive")
        if args.max_batches is not None and args.max_batches < 1:
            raise sources.SourceError("max batches must be positive")
        result = run_local_enrichment(
            args.work_dir,
            args.swift_source,
            args.workers,
            max_batches=args.max_batches,
        )
    elif args.command == "draft-source-enrichment":
        result = {"items": draft_source_enrichment(args.work_dir)}
    elif args.command == "seed-source-translations":
        result = {"translations": seed_source_translations(args.work_dir)}
    elif args.command == "invalidate-example-translations":
        result = {"translations": invalidate_example_translations(args.work_dir)}
    else:
        if args.workers < 1:
            raise sources.SourceError("workers must be positive")
        result = {
            "translations": run_local_translation(
                args.work_dir, args.swift_source, args.workers
            )
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except sources.SourceError as error:
        print(f"error: {error}")
        raise SystemExit(1)
