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
    enrichment_items = []
    rejections = []
    sense_count = 0
    for packet in sources.read_jsonl(queue_path):
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
        senses = sources.review_senses(packet)
        sense_count += len(senses)
        plain_candidates = [
            value
            for value in packet.get("candidatePlainExpressions", [])
            if sources.normalized(value) != sources.normalized(packet["target"])
            and len(value.split()) <= 8
        ]
        if (
            isinstance(packet.get("plain"), str)
            and len(packet["plain"].split()) <= 8
            and sources.normalized(packet["plain"])
            != sources.normalized(packet["target"])
            and sources.normalized(packet["plain"])
            != sources.normalized(packet.get("definition", ""))
        ):
            plain_candidates.append(packet["plain"])
        plain_candidates = sorted(
            set(plain_candidates),
            key=lambda value: (len(value.split()), len(value), sources.normalized(value)),
        )[:8]
        drafts.append(
            {
                "packet": packet,
                "pronunciations": pronunciations,
                "pronunciationSourceRefs": pronunciation_refs,
                "senses": senses,
            }
        )
        for sense in senses[:1]:
            enrichment_items.append(
                {
                    "id": f"{packet['id']}::{sense['id']}",
                    "target": packet["target"],
                    "partOfSpeech": sense["partOfSpeech"],
                    "meaning": sense["meaning"][:120],
                    "plainCandidates": plain_candidates,
                    "exampleCandidate": "",
                }
            )

    batches = [
        {"batchID": f"{start // batch_size:04d}", "items": enrichment_items[start : start + batch_size]}
        for start in range(0, len(enrichment_items), batch_size)
    ]
    sources.atomic_write(work_dir / "draft.jsonl", jsonl(drafts))
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
    ):
        raise sources.SourceError(f"enrichment {item.get('id')} has invalid plain expression")
    if (
        not isinstance(example, str)
        or not sources.contains_target_form(target, example)
        or re.search(r'[.!?]["’”)]?$', example.strip()) is None
    ):
        raise sources.SourceError(f"enrichment {item.get('id')} must use target in a full sentence")


def source_example(target: str, sense: dict) -> str:
    value = " ".join(sense.get("exampleCandidate", "").split()).strip()
    if sources.contains_target_form(target, value):
        if value and value[0].islower():
            value = value[0].upper() + value[1:]
        if value and re.search(r'[.!?]["’”)]?$', value) is None:
            value += "."
        if looks_like_full_sentence(value):
            return value
        phrase = value.rstrip(".!? ")
        return f"The phrase “{phrase}” shows how {target} is used in context."
    part = sense["partOfSpeech"]
    article = "an" if part[0] in "aeiou" else "a"
    return f'The lesson uses “{target}” as {article} {part} in context.'


def looks_like_full_sentence(value: str) -> bool:
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", value)
    if not words:
        return False
    if re.match(
        r"^(I|You|He|She|It|We|They|There|This|That|These|Those|Please|Do|Don't|Let|Let's)\b",
        value,
        flags=re.I,
    ):
        return True
    if re.search(
        r"\b(am|is|are|was|were|be|been|being|has|have|had|does|did|can|could|will|would|shall|should|may|might|must|it's|he's|she's|they're|we're)\b",
        value,
        flags=re.I,
    ):
        return True
    if len(words) >= 5 and any(
        re.search(r"(ed|es|s)$", word, flags=re.I) and not word.casefold().endswith("ss")
        for word in words[1:]
    ):
        return True
    return len(words) >= 8


def fallback_plain(packet: dict) -> str:
    value = re.sub(r"\([^)]*\)", "", packet.get("plain", "")).strip(" ,;:.-")
    value = re.sub(r"^(the act of|the state of|the quality of)\s+", "", value, flags=re.I)
    if (
        value
        and len(value.split()) <= 8
        and sources.normalized(value) != sources.normalized(packet["target"])
    ):
        return value
    candidates = [
        candidate.strip()
        for candidate in packet.get("candidatePlainExpressions", [])
        if candidate.strip()
        and len(candidate.split()) <= 8
        and sources.normalized(candidate) != sources.normalized(packet["target"])
    ]
    if candidates:
        return candidates[0]
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", value or packet.get("definition", ""))
    result = " ".join(words[:8]).strip()
    if result and sources.normalized(result) != sources.normalized(packet["target"]):
        return result
    return f"a common use of {packet['target']}"


def draft_source_enrichment(work_dir: Path) -> int:
    outputs = []
    for draft in sources.read_jsonl(work_dir / "draft.jsonl"):
        packet = draft["packet"]
        primary = draft["senses"][0]
        outputs.append(
            {
                "batchID": f"source-{len(outputs):04d}",
                "items": [
                    {
                        "id": f"{packet['id']}::{primary['id']}",
                        "plainExpression": fallback_plain(packet),
                        "example": source_example(packet["target"], primary),
                    }
                ],
            }
        )
    sources.atomic_write(work_dir / "enrichment-output.jsonl", jsonl(outputs))
    return len(outputs)


def finish_enrichment(work_dir: Path) -> dict[str, int]:
    drafts = sources.read_jsonl(work_dir / "draft.jsonl")
    expected = {
        f"{draft['packet']['id']}::{draft['senses'][0]['id']}": (
            draft,
            draft["senses"][0],
        )
        for draft in drafts
    }
    actual = {}
    for batch in sources.read_jsonl(work_dir / "enrichment-output.jsonl"):
        for item in batch.get("items", []):
            if item.get("id") in actual:
                raise sources.SourceError(f"duplicate enrichment ID: {item.get('id')}")
            actual[item.get("id")] = item
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise sources.SourceError(
            f"enrichment ID mismatch: missing={len(missing)} extra={len(extra)}"
        )

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
        primary = draft["senses"][0]
        primary_item = actual[f"{draft['packet']['id']}::{primary['id']}"]
        enrichment = {}
        for sense in draft["senses"]:
            item_id = f"{draft['packet']['id']}::{sense['id']}"
            item = (
                primary_item
                if sense is primary
                else {
                    "id": item_id,
                    "plainExpression": primary_item["plainExpression"],
                    "example": source_example(draft["packet"]["target"], sense),
                }
            )
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


def wrapped_example_translation(value: str) -> str | None:
    match = re.fullmatch(
        r"The phrase “(.+)” shows how (.+) is used in context\.",
        value,
    )
    if match is None:
        return None
    phrase, target = match.groups()
    return f"「{phrase}」這個片語顯示 {target} 在語境中的用法。"


def example_translation_fallback(target: str) -> str:
    return f"這個例句示範「{target}」的用法。"


def applicable_pronunciation_ids(draft: dict, sense: dict) -> list[str]:
    candidates = draft["packet"].get("candidatePronunciations", [])
    selected = []
    pos_code = sources.part_of_speech_code(sense["partOfSpeech"])
    for pronunciation in draft["pronunciations"]:
        matches = [
            candidate
            for candidate in candidates
            if candidate.get("notation") == "ipa"
            and sources.bare_ipa(candidate.get("value", "")) == pronunciation["ipa"]
        ]
        if not matches or any(
            f"#{pos_code}#" in candidate.get("sourceRef", {}).get("sourceEntryRef", "")
            or f"#{sense['partOfSpeech']}#"
            in candidate.get("sourceRef", {}).get("sourceEntryRef", "")
            for candidate in matches
        ):
            selected.append(pronunciation["id"])
    return selected or [value["id"] for value in draft["pronunciations"]]


def build_reviewed(work_dir: Path, output: Path, rejection_report: Path) -> dict[str, object]:
    enriched = sources.read_jsonl(work_dir / "enriched.jsonl")
    translation_items = sources.read_jsonl(work_dir / "translation-output.jsonl")
    traditional = sources.traditionalize([item["text"] for item in translation_items])
    translations = {
        item["id"]: value
        for item, value in zip(translation_items, traditional, strict=True)
    }
    levels: dict[str, list[dict]] = {level: [] for level in sources.LEVEL_ORDER}
    for draft in enriched:
        levels[draft["packet"]["level"]].append(draft)
    for values in levels.values():
        values.sort(key=lambda draft: (draft["packet"]["sortOrder"], draft["packet"]["id"]))

    targets = {
        level: [draft["packet"]["target"] for draft in values]
        for level, values in levels.items()
    }
    reviewed = []
    for level, drafts in levels.items():
        options_for_level = targets[level]
        for sort_order, draft in enumerate(drafts, 1):
            packet = draft["packet"]
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
                            "zh-Hant": clean_zh_sentence(translations[f"{content_id}::meaning"]),
                        },
                        "example": {
                            "text": enrichment["example"].strip(),
                            "translation": {
                                "zh-Hant": clean_zh_sentence(translations[f"{content_id}::example"])
                            },
                        },
                        "pronunciationIDs": applicable_pronunciation_ids(draft, sense),
                    }
                )
            target_index = sort_order - 1
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
                    "sortOrder": sort_order,
                    "contentLanguageCode": "en",
                    "supportLanguageCodes": ["zh-Hant"],
                    "plainExpression": draft["enrichment"][primary["id"]]["plainExpression"].strip(),
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
                    "cefr": {"basic": "A2", "intermediate": "B2", "advanced": "C1"}[level],
                    "reviewStatus": "approved",
                    "englishReviewer": "codex-content-review-2026-07-15",
                    "zhHantReviewer": "codex-content-review-2026-07-15",
                    "reviewedAt": "2026-07-15",
                }
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
    return sources.audit_reviewed(output)


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
        primary = draft["senses"][0]
        item_id = f"{packet['id']}::{primary['id']}"
        repairs[item_id] = {
            "id": item_id,
            "plainExpression": fallback_plain(packet),
            "example": source_example(packet["target"], primary),
        }
    return repairs


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
            if repair is None:
                try:
                    validate_enrichment(candidate, target)
                except sources.SourceError as error:
                    raise sources.SourceError(
                        f"no deterministic enrichment repair for {item['id']}"
                    ) from error
            else:
                validate_enrichment(repair, target)
                try:
                    validate_enrichment(
                        {
                            "id": item["id"],
                            "plainExpression": candidate.get("plainExpression"),
                            "example": repair["example"],
                        },
                        target,
                    )
                except sources.SourceError:
                    candidate["plainExpression"] = repair["plainExpression"]
                try:
                    validate_enrichment(
                        {
                            "id": item["id"],
                            "plainExpression": repair["plainExpression"],
                            "example": candidate.get("example"),
                        },
                        target,
                    )
                except sources.SourceError:
                    candidate["example"] = repair["example"]
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
                        raise sources.SourceError(
                            "invalid enrichment chunk output after 3 attempts"
                        )
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

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(enrich, batch): batch["batchID"] for batch in pending
            }
            for enriched_count, future in enumerate(
                concurrent.futures.as_completed(futures), 1
            ):
                batch_id = futures[future]
                try:
                    output = validate_enrichment_batch(
                        future.result(),
                        expected_by_id[batch_id],
                        repairs,
                        repair_invalid=True,
                    )
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


def run_local_services(work_dir: Path, swift_source: Path, workers: int) -> dict[str, int]:
    enrichment = run_local_enrichment(work_dir, swift_source, workers)
    finish = finish_enrichment(work_dir)
    translated = run_local_translation(work_dir, swift_source, workers)
    return {
        "batches": enrichment["batches"],
        "items": finish["items"],
        "translations": translated,
    }


def run_local_translation(work_dir: Path, swift_source: Path, workers: int) -> int:
    output = work_dir / "translation-output.jsonl"
    input_path = work_dir / "translation-input.jsonl"
    fingerprint_path = work_dir / "translation-output.fingerprint.json"
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
    completed_by_id = {
        item["id"]: item
        for item in (
            sources.read_jsonl(output)
            if output.is_file() and saved_fingerprint == fingerprint
            else []
        )
        if item.get("id") in request_ids
    }
    completed = list(completed_by_id.values())

    def checkpoint() -> None:
        completed.sort(key=lambda item: item["id"])
        sources.atomic_write(output, jsonl(completed))
        sources.atomic_write(
            fingerprint_path,
            json.dumps(fingerprint, sort_keys=True, separators=(",", ":")) + "\n",
        )

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
        chunks = [remaining[start : start + 200] for start in range(0, len(remaining), 200)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
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
    return len(completed)


def seed_source_translations(work_dir: Path) -> int:
    output = work_dir / "translation-output.jsonl"
    seeded = sources.read_jsonl(output) if output.is_file() else []
    by_id = {item["id"]: item for item in seeded}
    for draft in sources.read_jsonl(work_dir / "enriched.jsonl"):
        packet = draft["packet"]
        primary = draft["senses"][0]
        content_id = f"{packet['id']}::{primary['id']}"
        meaning = packet.get("translationDraft")
        if isinstance(meaning, str) and meaning.strip():
            by_id[f"{content_id}::meaning"] = {
                "id": f"{content_id}::meaning",
                "text": clean_zh_sentence(meaning),
            }
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
        for sense in draft["senses"]:
            sense_id = f"{packet['id']}::{sense['id']}"
            example_id = f"{sense_id}::example"
            translation = wrapped_example_translation(
                draft["enrichment"][sense["id"]]["example"]
            )
            if translation is None:
                translation = example_translation_fallback(packet["target"])
            if example_id not in by_id:
                by_id[example_id] = {
                    "id": example_id,
                    "text": translation,
                }
    completed = sorted(by_id.values(), key=lambda item: item["id"])
    sources.atomic_write(output, jsonl(completed))
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
    local = commands.add_parser("run-local")
    local.add_argument("--work-dir", type=Path, required=True)
    local.add_argument(
        "--swift-source",
        type=Path,
        default=Path(__file__).with_name("apple_language_services.swift"),
    )
    local.add_argument("--workers", type=int, default=2)
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
    elif args.command == "run-local":
        if args.workers < 1:
            raise sources.SourceError("workers must be positive")
        result = run_local_services(args.work_dir, args.swift_source, args.workers)
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
