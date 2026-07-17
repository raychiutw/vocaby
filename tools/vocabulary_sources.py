#!/usr/bin/env python3
"""Verify and normalize repository-only vocabulary sources."""

from __future__ import annotations

import argparse
import bz2
import csv
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Iterable


RIGHTS = (
    "commercialUse",
    "reproduction",
    "redistribution",
    "modification",
    "translatedDerivatives",
)
LEVEL_ORDER = {"basic": 0, "intermediate": 1, "advanced": 2}
CEFR_LEVEL = {
    "A1": "basic",
    "A2": "basic",
    "B1": "intermediate",
    "B2": "intermediate",
    "C1": "advanced",
    "C2": "advanced",
}
CEFR_ORDER = {value: index for index, value in enumerate(CEFR_LEVEL)}
LEARNER_UTILITY_ORDER = {
    "everyday": 0,
    "business": 1,
    "travel": 2,
    "practical-life": 3,
    "general": 4,
    "specialized": 5,
}
BLOCKED_SENSE_TAGS = {
    "archaic",
    "dated",
    "offensive",
    "obsolete",
    "rare",
    "slur",
    "uncommon",
}
ENGLISH_TERM = re.compile(r"^[A-Za-z][A-Za-z' -]{1,79}$")
ENGLISH_WORD = re.compile(r"[a-z]{3,}")
MEANING_STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "into",
    "not",
    "that",
    "the",
    "their",
    "this",
    "through",
    "with",
}
SENSE_TRANSLATION_OVERRIDES = {
    "i109294": "大量",
    "i110144": "陪伴",
    "i11061": "有節奏",
    "i15746": "呈現的",
    "i16205": "已婚",
    "i18090": "人畜共通",
    "i40766": "流程",
    "i67519": "誘人危險物",
    "i70529": "優先名單",
}
PARTS_OF_SPEECH = {
    "noun",
    "verb",
    "adjective",
    "adverb",
    "preposition",
    "conjunction",
    "interjection",
    "pronoun",
    "determiner",
    "phrase",
}
USAGE_NOTE_PREFIX = "例句中的"
SEED_KEYS = (
    "id",
    "level",
    "sortOrder",
    "contentLanguageCode",
    "supportLanguageCodes",
    "plainExpression",
    "upgradedExpression",
    "primarySenseID",
    "pronunciations",
    "senses",
    "quiz",
)


class SourceError(Exception):
    pass


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(str.maketrans("‘’‛–—−", "'''---"))
    return " ".join(value.casefold().split())


def _reviewed_evidence(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise SourceError(f"{label} must contain reviewed evidence")
    evidence = value.get("evidence")
    confidence = value.get("confidence")
    reviewer = value.get("reviewer")
    if (
        not isinstance(evidence, list)
        or not evidence
        or any(not isinstance(item, str) or not item.strip() for item in evidence)
        or isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0.8 <= confidence <= 1.0
        or not isinstance(reviewer, str)
        or not reviewer.strip()
    ):
        raise SourceError(f"{label} must contain reviewed evidence")
    return {
        "evidence": evidence,
        "confidence": confidence,
        "reviewer": reviewer,
    }


def cefr_evidence(candidate: dict) -> dict:
    exact = candidate.get("exactCEFREvidence", [])
    if not isinstance(exact, list):
        raise SourceError("exact CEFR evidence must be a list")
    if exact:
        values = {
            item.get("value")
            for item in exact
            if isinstance(item, dict) and item.get("value") in CEFR_LEVEL
        }
        if len(values) != 1 or len(values) != len({item.get("value") for item in exact}):
            raise SourceError("exact CEFR evidence must contain one unambiguous value")
        references = []
        reviewers = set()
        for item in exact:
            source_ref = item.get("sourceRef")
            if not isinstance(source_ref, dict) or not source_ref.get("sourceID"):
                raise SourceError("exact CEFR evidence must contain source references")
            references.append(json.dumps(source_ref, ensure_ascii=False, sort_keys=True))
            reviewers.add(source_ref["sourceID"])
        return {
            "value": next(iter(values)),
            "method": "exact",
            "evidence": sorted(set(references)),
            "confidence": 1.0,
            "reviewer": ",".join(sorted(reviewers)),
        }

    inferred = candidate.get("inferredCEFR")
    reviewed = _reviewed_evidence(inferred, "reviewed inferred CEFR")
    value = inferred.get("value")
    if value not in CEFR_LEVEL:
        raise SourceError("reviewed inferred CEFR must contain a valid value")
    return {"value": value, "method": "inferred", **reviewed}


def _learner_utility_evidence(candidate: dict) -> dict:
    utility = candidate.get("learnerUtility")
    if utility not in LEARNER_UTILITY_ORDER:
        raise SourceError("learner utility must use an approved category")
    raw_evidence = candidate.get("learnerUtilityEvidence")
    reviewed = _reviewed_evidence(raw_evidence, "learner utility")
    method = raw_evidence.get("method")
    if method not in {"exact", "inferred"}:
        raise SourceError("learner utility must contain an approved method")
    return {"value": utility, "method": method, **reviewed}


def _candidate_score(candidate: dict) -> tuple:
    cefr = cefr_evidence(candidate)
    frequency_rank = candidate.get("approvedFrequencyRank", sys.maxsize)
    occurrences = candidate.get("approvedCorpusOccurrences", 0)
    if isinstance(frequency_rank, bool) or not isinstance(frequency_rank, int):
        frequency_rank = sys.maxsize
    if isinstance(occurrences, bool) or not isinstance(occurrences, int):
        occurrences = 0
    source_refs = candidate.get("sourceRefs", [])
    first_source_ref = min(
        (json.dumps(item, ensure_ascii=False, sort_keys=True) for item in source_refs),
        default="",
    )
    return (
        LEARNER_UTILITY_ORDER[candidate["learnerUtility"]],
        max(0, frequency_rank),
        -max(0, occurrences),
        CEFR_ORDER[cefr["value"]],
        0 if cefr["method"] == "exact" else 1,
        -len(set(candidate.get("validationSourceIDs", []))),
        normalized(candidate["target"]),
        first_source_ref,
        json.dumps(candidate, ensure_ascii=False, sort_keys=True),
    )


def _eligible_target_candidate(candidate: object) -> bool:
    if not isinstance(candidate, dict):
        return False
    target = candidate.get("target")
    if (
        not isinstance(target, str)
        or ENGLISH_TERM.fullmatch(target) is None
        or len(target.split()) > 8
        or candidate.get("isProperName") is True
    ):
        return False
    senses = candidate.get("candidateSenses")
    pronunciations = candidate.get("candidatePronunciations")
    source_refs = candidate.get("sourceRefs")
    source_ids = candidate.get("validationSourceIDs")
    if (
        not isinstance(senses, list)
        or not senses
        or not isinstance(pronunciations, list)
        or not pronunciations
        or not isinstance(source_refs, list)
        or not source_refs
        or not isinstance(source_ids, list)
        or not source_ids
    ):
        return False
    for sense in senses:
        if not isinstance(sense, dict):
            return False
        glosses = sense.get("glosses")
        tags = {normalized(tag) for tag in sense.get("tags", []) if isinstance(tag, str)}
        if (
            sense.get("partOfSpeech") not in PARTS_OF_SPEECH
            or not isinstance(glosses, list)
            or not any(isinstance(gloss, str) and gloss.strip() for gloss in glosses)
            or tags & BLOCKED_SENSE_TAGS
        ):
            return False
    if any(
        not isinstance(item, dict)
        or item.get("notation") not in {"ipa", "arpabet"}
        or not isinstance(item.get("value"), str)
        or not item["value"].strip()
        for item in pronunciations
    ):
        return False
    try:
        _learner_utility_evidence(candidate)
        cefr_evidence(candidate)
    except SourceError:
        return False
    return True


def select_target_candidates(
    records: Iterable[dict], retained: Iterable[dict], target_count: int
) -> list[dict]:
    retained_items = []
    retained_keys = set()
    for item in retained:
        selected = dict(item)
        target = selected.get("target") or selected.get("upgradedExpression")
        if not isinstance(target, str) or not target.strip():
            raise SourceError("retained vocabulary must contain a target")
        key = normalized(target)
        if key in retained_keys:
            raise SourceError("retained vocabulary targets must be unique")
        retained_keys.add(key)
        selected["target"] = target
        retained_items.append(selected)
    if target_count < len(retained_items):
        raise SourceError("target count cannot be smaller than retained vocabulary")

    candidates_by_key: dict[str, dict] = {}
    for candidate in records:
        if not _eligible_target_candidate(candidate):
            continue
        key = normalized(candidate["target"])
        if key in retained_keys:
            continue
        current = candidates_by_key.get(key)
        if current is None or _candidate_score(candidate) < _candidate_score(current):
            candidates_by_key[key] = candidate

    candidates = sorted(candidates_by_key.values(), key=_candidate_score)
    needed = target_count - len(retained_items)
    if len(candidates) < needed:
        raise SourceError(
            f"only {len(candidates)} eligible candidates for {needed} open targets"
        )
    selected_items = retained_items
    for candidate in candidates[:needed]:
        selected = dict(candidate)
        cefr = cefr_evidence(candidate)
        selected["cefr"] = cefr["value"]
        selected["level"] = CEFR_LEVEL[cefr["value"]]
        selected["cefrEvidence"] = cefr
        selected["learnerUtilityEvidence"] = _learner_utility_evidence(candidate)
        selected_items.append(selected)
    return selected_items


BUSINESS_UTILITY_WORDS = {
    "account",
    "agreement",
    "budget",
    "business",
    "client",
    "company",
    "contract",
    "customer",
    "deadline",
    "employee",
    "employer",
    "finance",
    "invoice",
    "market",
    "meeting",
    "office",
    "payment",
    "price",
    "project",
    "sale",
    "service",
    "supplier",
    "tax",
    "team",
    "work",
}
TRAVEL_UTILITY_WORDS = {
    "airport",
    "arrival",
    "baggage",
    "booking",
    "border",
    "bus",
    "departure",
    "destination",
    "flight",
    "hotel",
    "journey",
    "luggage",
    "passport",
    "reservation",
    "restaurant",
    "station",
    "ticket",
    "tour",
    "tourist",
    "train",
    "travel",
    "trip",
    "visa",
}
PRACTICAL_UTILITY_WORDS = {
    "bank",
    "bathroom",
    "breakfast",
    "child",
    "clinic",
    "clothes",
    "doctor",
    "emergency",
    "family",
    "food",
    "health",
    "home",
    "hospital",
    "house",
    "insurance",
    "meal",
    "medicine",
    "money",
    "phone",
    "rent",
    "school",
    "shop",
    "shopping",
    "store",
    "street",
}
TARGET_REVIEWER = "vocaby-taiwan-learner-rubric-v1"


def _iter_jsonl(path: Path) -> Iterable[dict]:
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as error:
                    raise SourceError(
                        f"invalid JSONL {path}:{line_number}: {error}"
                    ) from error
                if not isinstance(value, dict):
                    raise SourceError(f"JSONL row must be an object: {path}:{line_number}")
                yield value
    except OSError as error:
        raise SourceError(f"cannot read JSONL {path}: {error}") from error


def _retained_items(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return list(_iter_jsonl(path))
    value = load_json(path, list)
    if any(not isinstance(item, dict) for item in value):
        raise SourceError("retained vocabulary must contain objects")
    return value


def _canonical_source_ref(record: dict) -> dict:
    return {
        "sourceID": record["sourceID"],
        "sourceEntryRef": record["sourceEntryRef"],
    }


def _candidate_senses(record: dict, source_ref: dict) -> list[dict]:
    result = []
    senses = record.get("senses")
    if isinstance(senses, list) and senses:
        for index, sense in enumerate(senses, 1):
            if not isinstance(sense, dict):
                continue
            glosses = sense.get("glosses")
            if not isinstance(glosses, list) or not glosses:
                continue
            result.append(
                {
                    "id": str(sense.get("id") or f"{record['sourceEntryRef']}:{index}"),
                    "partOfSpeech": canonical_part_of_speech(
                        sense.get("partOfSpeech") or record.get("partOfSpeech")
                    ),
                    "glosses": [
                        value.strip()
                        for value in glosses
                        if isinstance(value, str) and value.strip()
                    ],
                    "examples": [
                        value.strip()
                        for value in sense.get("examples", [])
                        if isinstance(value, str) and value.strip()
                    ],
                    "tags": sorted(
                        {
                            normalized(value)
                            for value in sense.get("tags", [])
                            if isinstance(value, str) and value.strip()
                        }
                    ),
                    "sourceRef": source_ref,
                }
            )
        return result

    definitions = record.get("definitions")
    if not isinstance(definitions, list):
        return []
    examples = [
        value.strip()
        for value in record.get("examples", [])
        if isinstance(value, str) and value.strip()
    ]
    for index, definition in enumerate(definitions, 1):
        if not isinstance(definition, str) or not definition.strip():
            continue
        result.append(
            {
                "id": f"{record['sourceEntryRef']}:{index}",
                "partOfSpeech": canonical_part_of_speech(record.get("partOfSpeech")),
                "glosses": [definition.strip()],
                "examples": examples[:1],
                "tags": [],
                "sourceRef": source_ref,
            }
        )
    return result


def _approved_cefr_evidence(values: list[dict]) -> list[dict]:
    valid = [item for item in values if item.get("value") in CEFR_LEVEL]
    if not valid:
        return []
    preferred_value = min((item["value"] for item in valid), key=CEFR_ORDER.__getitem__)
    return sorted(
        (item for item in valid if item["value"] == preferred_value),
        key=lambda item: json.dumps(item["sourceRef"], sort_keys=True),
    )


def _utility_for_candidate(candidate: dict) -> tuple[str, dict]:
    exact = _approved_cefr_evidence(candidate.get("exactCEFREvidence", []))
    corpus_occurrences = candidate.get("approvedCorpusOccurrences", 0)
    words = set(
        re.findall(
            r"[a-z]+",
            " ".join(
                [candidate["target"]]
                + [
                    gloss
                    for sense in candidate["candidateSenses"]
                    for gloss in sense.get("glosses", [])
                ]
            ).casefold(),
        )
    )
    if exact and exact[0]["value"] in {"A1", "A2"}:
        utility = "everyday"
        method = "exact"
        evidence = [
            f"{exact[0]['value']}:{exact[0]['sourceRef']['sourceID']}:"
            f"{exact[0]['sourceRef']['sourceEntryRef']}"
        ]
        confidence = 1.0
        reviewer = exact[0]["sourceRef"]["sourceID"]
    else:
        matched = None
        for utility, keywords in (
            ("business", BUSINESS_UTILITY_WORDS),
            ("travel", TRAVEL_UTILITY_WORDS),
            ("practical-life", PRACTICAL_UTILITY_WORDS),
        ):
            overlap = sorted(words & keywords)
            if overlap:
                matched = (utility, overlap)
                break
        if corpus_occurrences >= 5:
            utility = "everyday"
            evidence = [f"approved-corpus-occurrences:{corpus_occurrences}"]
        elif matched is not None:
            utility, overlap = matched
            evidence = [f"reviewed-domain-keywords:{','.join(overlap)}"]
        elif corpus_occurrences or (exact and exact[0]["value"] in {"B1", "B2"}):
            utility = "general"
            evidence = [f"approved-corpus-occurrences:{corpus_occurrences}"]
        else:
            utility = "specialized"
            evidence = ["no-approved-general-corpus-occurrence"]
        method = "inferred"
        confidence = 0.8
        reviewer = TARGET_REVIEWER
    return utility, {
        "method": method,
        "evidence": evidence,
        "confidence": confidence,
        "reviewer": reviewer,
    }


def _inferred_cefr(candidate: dict) -> dict:
    occurrences = candidate.get("approvedCorpusOccurrences", 0)
    utility = candidate["learnerUtility"]
    if occurrences >= 25:
        value = "A2"
    elif occurrences >= 5 or utility == "everyday":
        value = "B1"
    elif utility in {"business", "travel", "practical-life"}:
        value = "B2"
    elif utility == "general":
        value = "C1"
    else:
        value = "C2"
    return {
        "value": value,
        "evidence": [
            f"learner-utility:{utility}",
            f"approved-corpus-occurrences:{occurrences}",
        ],
        "confidence": 0.8,
        "reviewer": TARGET_REVIEWER,
    }


def _corpus_occurrences(
    input_dir: Path, corpus_source_ids: set[str], candidate_keys: set[str]
) -> dict[str, int]:
    lengths = {len(key.split()) for key in candidate_keys}
    counts: dict[str, int] = {}
    for path in sorted(input_dir.glob("*.jsonl")):
        for record in _iter_jsonl(path):
            if record.get("sourceID") not in corpus_source_ids:
                continue
            tokens = re.findall(r"[a-z]+(?:'[a-z]+)?", normalized(record.get("headword", "")))
            for length in lengths:
                for index in range(len(tokens) - length + 1):
                    key = " ".join(tokens[index : index + length])
                    if key in candidate_keys:
                        counts[key] = counts.get(key, 0) + 1
    return counts


def assemble_target_candidates(
    input_dir: Path,
    approved_source_ids: set[str],
    corpus_source_ids: set[str],
) -> list[dict]:
    grouped: dict[str, dict] = {}
    for path in sorted(input_dir.glob("*.jsonl")):
        for record in _iter_jsonl(path):
            source_id = record.get("sourceID")
            if source_id not in approved_source_ids or source_id in corpus_source_ids:
                continue
            headword = record.get("headword")
            if not isinstance(headword, str):
                continue
            key = normalized(headword)
            if ENGLISH_TERM.fullmatch(key) is None or len(key.split()) > 8:
                continue
            source_entry_ref = record.get("sourceEntryRef")
            if not isinstance(source_entry_ref, str) or not source_entry_ref:
                continue
            source_ref = _canonical_source_ref(record)
            candidate = grouped.setdefault(
                key,
                {
                    "target": key,
                    "candidateSenses": [],
                    "candidatePronunciations": [],
                    "candidatePlainExpressions": [],
                    "validationSourceIDs": [],
                    "sourceRefs": [],
                    "exactCEFREvidence": [],
                    "isProperName": False,
                },
            )
            candidate["sourceRefs"].append(source_ref)
            candidate["validationSourceIDs"].append(source_id)
            candidate["candidatePlainExpressions"].extend(
                value
                for value in record.get("forms", [])
                if isinstance(value, str) and value.strip()
            )
            candidate["candidateSenses"].extend(_candidate_senses(record, source_ref))
            candidate["isProperName"] |= normalized(record.get("partOfSpeech") or "") in {
                "name",
                "proper noun",
                "proper-noun",
            }
            for pronunciation in record.get("pronunciations", []):
                if not isinstance(pronunciation, dict):
                    continue
                value = pronunciation.get("value")
                notation = pronunciation.get("notation")
                if notation not in {"ipa", "arpabet"} or not isinstance(value, str):
                    continue
                candidate["candidatePronunciations"].append(
                    {**pronunciation, "sourceRef": source_ref}
                )
            if record.get("cefr") in CEFR_LEVEL:
                candidate["exactCEFREvidence"].append(
                    {"value": record["cefr"], "sourceRef": source_ref}
                )

    corpus_counts = _corpus_occurrences(input_dir, corpus_source_ids, set(grouped))
    for key, candidate in grouped.items():
        candidate["sourceRefs"] = merged_list(candidate["sourceRefs"])
        candidate["validationSourceIDs"] = sorted(
            set(candidate["validationSourceIDs"])
        )
        candidate["candidatePlainExpressions"] = sorted(
            set(candidate["candidatePlainExpressions"]), key=normalized
        )[:8]
        senses = {
            (
                sense["partOfSpeech"],
                tuple(sense["glosses"]),
                tuple(sense["tags"]),
            ): sense
            for sense in candidate["candidateSenses"]
            if not set(sense["tags"]) & BLOCKED_SENSE_TAGS
        }
        candidate["candidateSenses"] = sorted(
            senses.values(),
            key=lambda sense: (
                json.dumps(sense["sourceRef"], sort_keys=True),
                sense["id"],
            ),
        )[:3]
        pronunciations = {
            (
                item["notation"],
                item["value"],
                item.get("region", ""),
            ): item
            for item in candidate["candidatePronunciations"]
        }
        candidate["candidatePronunciations"] = sorted(
            pronunciations.values(),
            key=lambda item: (
                item["notation"],
                item["value"],
                json.dumps(item["sourceRef"], sort_keys=True),
            ),
        )[:3]
        candidate["exactCEFREvidence"] = _approved_cefr_evidence(
            candidate["exactCEFREvidence"]
        )
        candidate["approvedCorpusOccurrences"] = corpus_counts.get(key, 0)

    ranked_keys = sorted(
        grouped,
        key=lambda key: (-grouped[key]["approvedCorpusOccurrences"], key),
    )
    for rank, key in enumerate(ranked_keys, 1):
        candidate = grouped[key]
        candidate["approvedFrequencyRank"] = (
            rank if candidate["approvedCorpusOccurrences"] else sys.maxsize
        )
        utility, evidence = _utility_for_candidate(candidate)
        candidate["learnerUtility"] = utility
        candidate["learnerUtilityEvidence"] = evidence
        if not candidate["exactCEFREvidence"]:
            candidate["inferredCEFR"] = _inferred_cefr(candidate)
    return list(grouped.values())


def prepare_100k(
    input_dir: Path,
    retained_path: Path,
    output: Path,
    approved_source_ids: set[str],
    *,
    target_count: int = 100_000,
    reserve_count: int = 10_000,
    corpus_source_ids: set[str] | None = None,
) -> dict[str, int]:
    if target_count < 1 or reserve_count < 0:
        raise SourceError("target and reserve counts must be non-negative")
    retained = _retained_items(retained_path)
    if len(retained) > target_count:
        raise SourceError("retained vocabulary exceeds target count")
    candidates = assemble_target_candidates(
        input_dir,
        approved_source_ids,
        corpus_source_ids or {"tatoeba-eng-cmn-2026-07-04"},
    )
    selected = select_target_candidates(
        candidates,
        retained,
        target_count=target_count + reserve_count,
    )
    queue = selected[len(retained) :]
    required_new = target_count - len(retained)
    next_sort_order = {level: 1 for level in LEVEL_ORDER}
    for item in retained:
        level = item.get("level")
        sort_order = item.get("sortOrder")
        if level in next_sort_order and isinstance(sort_order, int):
            next_sort_order[level] = max(next_sort_order[level], sort_order + 1)
    for rank, item in enumerate(queue, 1):
        item["id"] = "vocab-" + hashlib.sha256(
            normalized(item["target"]).encode("utf-8")
        ).hexdigest()[:16]
        item["selectionRank"] = rank
        item["selectionStatus"] = "target" if rank <= required_new else "reserve"
        item["sortOrder"] = next_sort_order[item["level"]]
        next_sort_order[item["level"]] += 1
    atomic_write(
        output,
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in queue
        ),
    )
    return {
        "retained": len(retained),
        "target": required_new,
        "reserve": reserve_count,
    }


def targets_to_seed(input_path: Path, output: Path) -> int:
    targets = {}
    for item in _iter_jsonl(input_path):
        target = item.get("target") or item.get("upgradedExpression")
        if not isinstance(target, str) or not target.strip():
            raise SourceError("target queue row must contain a target")
        key = normalized(target)
        if key in targets:
            raise SourceError(f"duplicate target queue expression: {target}")
        targets[key] = target.strip()
    ordered = [
        {"upgradedExpression": targets[key]}
        for key in sorted(targets)
    ]
    atomic_write(
        output,
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
    )
    return len(ordered)


def load_manifest(root: Path) -> dict:
    path = root / "Content/Sources/source-manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceError(f"cannot read manifest {path}: {error}") from error
    if manifest.get("schemaVersion") != 1 or not isinstance(manifest.get("sources"), list):
        raise SourceError("source manifest must use schemaVersion 1 and contain sources")
    ids = [source.get("id") for source in manifest["sources"]]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise SourceError("source manifest IDs must be non-empty and unique")
    return manifest


def selected_sources(manifest: dict, source_id: str | None) -> list[dict]:
    sources = manifest["sources"]
    if source_id is None:
        return sources
    selected = [source for source in sources if source["id"] == source_id]
    if not selected:
        raise SourceError(f"unknown source: {source_id}")
    return selected


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_raw_file(root: Path, source_id: str, raw: dict) -> Path:
    required = ("path", "sha256", "bytes")
    if any(key not in raw for key in required):
        raise SourceError(f"{source_id}: raw file is incomplete")
    path = root / raw["path"]
    if not path.is_file():
        raise SourceError(f"{source_id}: missing raw file {raw['path']}")
    if path.stat().st_size != raw["bytes"]:
        raise SourceError(f"{source_id}: byte count mismatch")
    if sha256(path) != raw["sha256"]:
        raise SourceError(f"{source_id}: checksum mismatch")
    return path


def verify_source(root: Path, source: dict) -> Path | list[Path]:
    if "rawFiles" in source:
        raw_files = source["rawFiles"]
        if not isinstance(raw_files, list) or not raw_files:
            raise SourceError(f"{source['id']}: rawFiles must be a non-empty list")
        paths = [verify_raw_file(root, source["id"], raw) for raw in raw_files]
    else:
        paths = [verify_raw_file(root, source["id"], source.get("rawFile", {}))]
    for evidence in source.get("licenseEvidence", []):
        record = {"path": evidence} if isinstance(evidence, str) else evidence
        evidence_path = root / record.get("path", "")
        if not evidence_path.is_file():
            raise SourceError(f"{source['id']}: missing license evidence {record.get('path')}")
        if "bytes" in record and evidence_path.stat().st_size != record["bytes"]:
            raise SourceError(f"{source['id']}: license evidence byte count mismatch")
        if "sha256" in record and sha256(evidence_path) != record["sha256"]:
            raise SourceError(f"{source['id']}: license evidence checksum mismatch")
    if source.get("repositoryRedistribution") not in {"allowed", "review_required"}:
        raise SourceError(f"{source['id']}: repository redistribution is not declared")
    return paths if len(paths) > 1 else paths[0]


def empty_record(source_id: str, reference: str, headword: str) -> dict:
    return {
        "sourceID": source_id,
        "sourceEntryRef": reference,
        "headword": headword.strip(),
        "partOfSpeech": None,
        "cefr": None,
        "definitions": [],
        "examples": [],
        "relatedTerms": [],
        "translations": {},
        "pronunciations": [],
        "senses": [],
        "forms": [],
        "senseRefs": [],
        "iliRefs": [],
    }


def parse_lemma_csv(path: Path, source_id: str, encoding: str = "utf-8-sig") -> Iterable[dict]:
    with path.open(encoding=encoding, newline="") as stream:
        for row in csv.reader(stream):
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            headword = row[0].strip()
            record = empty_record(source_id, normalized(headword), headword)
            record["forms"] = [value.strip() for value in row[1:] if value.strip()]
            yield record


def parse_cmudict(path: Path, source_id: str) -> Iterable[dict]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip() or line.startswith(";;; "):
                continue
            word, pronunciation = line.rstrip().split(maxsplit=1)
            pronunciation = pronunciation.partition(" #")[0].strip()
            if not pronunciation:
                continue
            headword = re.sub(r"\(\d+\)$", "", word)
            record = empty_record(source_id, normalized(headword), headword)
            record["pronunciations"] = [
                {
                    "notation": "arpabet",
                    "value": pronunciation,
                    "speechLocale": "en-US",
                    "region": "US",
                    "tags": [],
                }
            ]
            yield record


MOBY_PHONE_IPA = {
    "(@)": "ɛɹ",
    "[@]": "ɝ",
    "eI": "eɪ",
    "aI": "aɪ",
    "Oi": "ɔɪ",
    "AU": "aʊ",
    "oU": "oʊ",
    "Ou": "oʊ",
    "tS": "tʃ",
    "dZ": "dʒ",
    "hw": "ʍ",
    "&": "æ",
    "A": "ɑ",
    "@": "ə",
    "-": "ə",
    "E": "ɛ",
    "i": "i",
    "I": "ɪ",
    "O": "ɔ",
    "u": "u",
    "U": "ʊ",
    "N": "ŋ",
    "S": "ʃ",
    "T": "θ",
    "D": "ð",
    "Z": "ʒ",
    "R": "ʁ",
    "Y": "y",
    "y": "ø",
    "W": "ʍ",
    "V": "v",
    "c": "c",
    "x": "x",
    "a": "a",
    "e": "e",
    "o": "o",
    "r": "ɹ",
    "'": "ˈ",
    ",": "ˌ",
    "_": " ",
    " ": " ",
    **{value: value for value in "bdfghjklmnpstvwz"},
}
MOBY_PHONE_TOKENS = sorted(MOBY_PHONE_IPA, key=len, reverse=True)
MOBY_PARTS_OF_SPEECH = {
    "n": "noun",
    "v": "verb",
    "av": "adverb",
    "aj": "adjective",
    "inj": "interjection",
    "interj": "interjection",
    "prp": "preposition",
}
MOBY_3205_REJECTED_ENTRIES = {
    "antivivisectionist",
    "eery",
    "Eifel",
    "Gyula_Alapi",
    "Idria",
    "mastoparietal",
    "microcephalism",
    "precancerous",
    "preoperative",
    "Rauschenbusch",
    "respire",
    "treble",
    "turtle-dove",
    "verdant",
    "Xinhua",
}


def moby_to_ipa(notation: str) -> str:
    ipa = []
    index = 0
    while index < len(notation):
        if notation[index] == "/":
            index += 1
            continue
        token = next(
            (value for value in MOBY_PHONE_TOKENS if notation.startswith(value, index)),
            None,
        )
        if token is None:
            raise SourceError(
                f"unknown Moby notation at {notation[index:]!r} in {notation!r}"
            )
        ipa.append(MOBY_PHONE_IPA[token])
        index += len(token)
    return " ".join("".join(ipa).split())


def parse_moby_pronunciator(path: Path, source_id: str) -> Iterable[dict]:
    with path.open(encoding="mac_roman", newline="") as stream:
        for line_number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry, notation = line.split(maxsplit=1)
            except ValueError as error:
                raise SourceError(
                    f"invalid Moby record at line {line_number}: {line!r}"
                ) from error
            if (
                source_id == "moby-pronunciator-ii-3205"
                and entry in MOBY_3205_REJECTED_ENTRIES
            ):
                continue
            headword_entry, separator, suffix = entry.rpartition("/")
            part_of_speech = MOBY_PARTS_OF_SPEECH.get(suffix) if separator else None
            headword = (headword_entry if part_of_speech else entry).replace("_", " ")
            record = empty_record(source_id, entry, headword)
            record["partOfSpeech"] = part_of_speech
            record["pronunciations"] = [
                {
                    "notation": "ipa",
                    "value": moby_to_ipa(notation),
                    "speechLocale": "en-US",
                    "region": "General",
                    "tags": [],
                }
            ]
            yield record


def parse_grundwortschatz_sqlite_gzip(path: Path, source_id: str) -> Iterable[dict]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temporary:
        temporary_path = Path(temporary.name)
        with gzip.open(path, "rb") as compressed:
            shutil.copyfileobj(compressed, temporary)
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            rows = connection.execute(
                "SELECT original_id, word, lemma, word_type, enrichment_json, metadata_json FROM words"
            )
            for reference, word, lemma, part_of_speech, enrichment_json, metadata_json in rows:
                metadata = json.loads(metadata_json or "{}")
                cefr = metadata.get("cefr_level")
                if cefr not in CEFR_LEVEL and metadata.get("gradeLevelEstimate") in {5, 6}:
                    cefr = "C1"
                if cefr not in CEFR_LEVEL:
                    continue
                headword = (lemma or word or "").strip()
                if ENGLISH_TERM.fullmatch(headword) is None:
                    continue
                enrichment = json.loads(enrichment_json or "{}")
                record = empty_record(source_id, reference, headword)
                record["partOfSpeech"] = canonical_part_of_speech(part_of_speech)
                record["cefr"] = cefr
                record["definitions"] = [
                    value.strip()
                    for value in enrichment.get("definitions", [])
                    if isinstance(value, str) and value.strip()
                ]
                record["examples"] = list(dict.fromkeys(
                    value.strip()
                    for value in [
                        *enrichment.get("examples", []),
                        *metadata.get("gutenberg_examples", []),
                    ]
                    if isinstance(value, str) and value.strip()
                ))
                pronunciation = metadata.get("pronunciation", {})
                ipa = pronunciation.get("ipa") if isinstance(pronunciation, dict) else None
                if isinstance(ipa, str) and ipa.strip():
                    record["pronunciations"] = [{
                        "notation": "ipa",
                        "value": ipa.strip(),
                        "speechLocale": "en-US",
                        "region": "US" if pronunciation.get("source") == "cmudict" else None,
                        "tags": [],
                    }]
                yield record
        finally:
            connection.close()
    finally:
        temporary_path.unlink(missing_ok=True)


def parse_cow(path: Path, source_id: str) -> Iterable[dict]:
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip() or line.startswith("#"):
                continue
            synset, _, lemma = line.rstrip("\n").split("\t", 2)
            record = empty_record(source_id, f"{synset}:{normalized(lemma)}", lemma)
            record["senseRefs"] = [synset]
            record["translations"] = {"language": "cmn"}
            yield record


def parse_oewn(path: Path, source_id: str) -> Iterable[dict]:
    with zipfile.ZipFile(path) as archive:
        synsets = {}
        for name in sorted(
            value
            for value in archive.namelist()
            if value.endswith(".json")
            and not value.startswith("entries-")
            and value != "frames.json"
        ):
            with archive.open(name) as stream:
                for synset_id, data in json.load(stream).items():
                    synsets[synset_id] = {
                        "definitions": data.get("definition", []),
                        "examples": [
                            value if isinstance(value, str) else value.get("text", "")
                            for value in data.get("example", [])
                            if isinstance(value, str) or value.get("text")
                        ],
                        "relatedTerms": data.get("members", []),
                        "iliRefs": [data["ili"]] if data.get("ili") else [],
                    }
        for name in sorted(value for value in archive.namelist() if value.startswith("entries-") and value.endswith(".json")):
            with archive.open(name) as stream:
                entries = json.load(stream)
            for headword, parts in entries.items():
                for part_of_speech, data in parts.items():
                    pronunciations = [
                        item["value"] for item in data.get("pronunciation", []) if item.get("value")
                    ]
                    for sense in data.get("sense", []):
                        synset_id = sense.get("synset")
                        if not synset_id:
                            continue
                        reference = f"{normalized(headword)}#{part_of_speech}#{synset_id}"
                        record = empty_record(source_id, reference, headword)
                        record["partOfSpeech"] = part_of_speech
                        record["pronunciations"] = pronunciations
                        record["senseRefs"] = [synset_id]
                        synset = synsets.get(synset_id, {})
                        record["definitions"].extend(synset.get("definitions", []))
                        record["examples"].extend(synset.get("examples", []))
                        record["relatedTerms"].extend(synset.get("relatedTerms", []))
                        record["iliRefs"].extend(synset.get("iliRefs", []))
                        yield record


def xlsx_rows(data: bytes, sheet_name: str) -> Iterable[list[str]]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    office_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with zipfile.ZipFile(io.BytesIO(data)) as workbook:
        shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
        shared = ["".join(item.itertext()) for item in shared_root.findall("x:si", ns)]
        book_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        sheet = next((item for item in book_root.findall("x:sheets/x:sheet", ns) if item.get("name") == sheet_name), None)
        if sheet is None:
            raise SourceError(f"XLSX sheet not found: {sheet_name}")
        relation_id = sheet.get(office_rel)
        rel_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        relation = next((item for item in rel_root.findall("r:Relationship", rel_ns) if item.get("Id") == relation_id), None)
        if relation is None:
            raise SourceError(f"XLSX relationship not found: {relation_id}")
        target = relation.get("Target", "").lstrip("/")
        target = target if target.startswith("xl/") else f"xl/{target}"
        root = ET.fromstring(workbook.read(target))
        for row in root.findall("x:sheetData/x:row", ns):
            values: dict[int, str] = {}
            for cell in row.findall("x:c", ns):
                reference = cell.get("r", "A1")
                column = 0
                for character in re.match(r"[A-Z]+", reference).group():
                    column = column * 26 + ord(character) - 64
                value = cell.findtext("x:v", default="", namespaces=ns)
                if cell.get("t") == "s" and value:
                    value = shared[int(value)]
                values[column - 1] = value
            yield [values.get(index, "") for index in range(max(values, default=-1) + 1)]


def parse_cefr_j(path: Path, source_id: str) -> Iterable[dict]:
    with zipfile.ZipFile(path) as outer:
        xlsx_name = next((name for name in outer.namelist() if name.lower().endswith(".xlsx")), None)
        if xlsx_name is None:
            raise SourceError("CEFR-J archive does not contain an XLSX file")
        rows = iter(xlsx_rows(outer.read(xlsx_name), "ALL"))
    next(rows, None)
    for row in rows:
        if len(row) < 3 or not row[0].strip():
            continue
        headword, part_of_speech, cefr = (value.strip() for value in row[:3])
        reference = "#".join((normalized(headword), normalized(part_of_speech), cefr))
        record = empty_record(source_id, reference, headword)
        record["partOfSpeech"] = part_of_speech or None
        record["cefr"] = cefr or None
        yield record


def parse_freedict(path: Path, source_id: str) -> Iterable[dict]:
    ns = {"t": "http://www.tei-c.org/ns/1.0"}
    with tarfile.open(path, "r:*") as archive:
        member = next((item for item in archive.getmembers() if item.name.endswith(".tei")), None)
        if member is None:
            raise SourceError("FreeDict archive does not contain TEI")
        stream = archive.extractfile(member)
        if stream is None:
            raise SourceError("FreeDict TEI cannot be read")
        root = ET.parse(stream).getroot()
    for index, entry in enumerate(root.findall(".//t:entry", ns), start=1):
        headword = entry.findtext("t:form/t:orth", default="", namespaces=ns).strip()
        if not headword:
            continue
        part_of_speech = entry.findtext("t:gramGrp/t:pos", default="", namespaces=ns) or None
        pronunciations = [
            value.text.strip()
            for value in entry.findall("t:form/t:pron", ns)
            if value.text and value.text.strip()
        ]
        senses = entry.findall("t:sense", ns) or [entry]
        for sense_index, sense in enumerate(senses, start=1):
            record = empty_record(
                source_id, f"entry-{index}-sense-{sense_index}", headword
            )
            record["partOfSpeech"] = part_of_speech
            record["pronunciations"] = pronunciations
            record["definitions"] = [
                value.text.strip()
                for value in sense.findall(".//t:def", ns)
                if value.text and value.text.strip()
            ]
            record["translations"] = {
                "zh": [
                    value.text.strip()
                    for value in sense.findall('.//t:cit[@type="trans"]/t:quote', ns)
                    if value.text and value.text.strip()
                ]
            }
            yield record


def parse_gcide(path: Path, source_id: str) -> Iterable[dict]:
    pattern = re.compile(r"<ent>(.*?)</ent>", re.IGNORECASE | re.DOTALL)
    with tarfile.open(path, "r:*") as archive:
        for member in sorted((item for item in archive.getmembers() if re.search(r"/CIDE\.[A-Z]$", item.name)), key=lambda item: item.name):
            stream = archive.extractfile(member)
            if stream is None:
                continue
            text = stream.read().decode("utf-8", errors="replace")
            for match in pattern.finditer(text):
                headword = re.sub(r"<[^>]+>", "", match.group(1)).strip()
                if headword:
                    yield empty_record(source_id, normalized(headword), headword)


CEDICT_LINE = re.compile(r"^(\S+)\s+(\S+)\s+\[[^]]*\]\s+/(.*)/$")
CEDICT_GLOSS = re.compile(r"[A-Za-z][A-Za-z '\-]*")
CEDICT_NOISE_PREFIXES = (
    "abbr. for ",
    "also written ",
    "classifier for ",
    "erhua variant ",
    "old variant of ",
    "see ",
    "surname ",
    "used in ",
    "variant of ",
)


def parse_cedict(path: Path, source_id: str) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.startswith("#"):
                continue
            match = CEDICT_LINE.match(line.rstrip("\n"))
            if match is None:
                continue
            traditional, _, body = match.groups()
            glosses = []
            for raw_gloss in body.split("/"):
                gloss = re.sub(r"^to\s+", "", raw_gloss.strip(), flags=re.IGNORECASE)
                lowered = gloss.casefold()
                if (
                    not gloss
                    or any(lowered.startswith(prefix) for prefix in CEDICT_NOISE_PREFIXES)
                    or "|" in gloss
                    or "[" in gloss
                    or "CL:" in gloss
                    or len(gloss) > 60
                    or len(gloss.split()) > 7
                    or CEDICT_GLOSS.fullmatch(gloss) is None
                ):
                    continue
                glosses.append(gloss.casefold())
            glosses = sorted(set(glosses), key=lambda value: (normalized(value), value))
            for gloss in glosses:
                record = empty_record(
                    source_id,
                    f"line-{line_number}:{normalized(gloss)}",
                    gloss,
                )
                record["definitions"] = glosses
                record["translations"] = {"zh-Hant": [traditional]}
                yield record


def parse_tatoeba(paths: list[Path], source_id: str) -> Iterable[dict]:
    by_name = {path.name: path for path in paths}
    required = {
        "eng_sentences.tsv.bz2",
        "cmn_sentences.tsv.bz2",
        "cmn-eng_links.tsv.bz2",
    }
    missing = required - set(by_name)
    if missing:
        raise SourceError(
            f"{source_id}: missing Tatoeba file(s): {', '.join(sorted(missing))}"
        )

    links: dict[int, list[int]] = {}
    with bz2.open(by_name["cmn-eng_links.tsv.bz2"], "rt", encoding="utf-8") as stream:
        for line in stream:
            chinese_id, english_id = line.rstrip("\n").split("\t")
            links.setdefault(int(english_id), []).append(int(chinese_id))

    chinese_ids = {value for values in links.values() for value in values}
    chinese: dict[int, str] = {}
    with bz2.open(by_name["cmn_sentences.tsv.bz2"], "rt", encoding="utf-8") as stream:
        for line in stream:
            sentence_id, _, sentence = line.rstrip("\n").split("\t", 2)
            numeric_id = int(sentence_id)
            if numeric_id in chinese_ids:
                chinese[numeric_id] = sentence

    with bz2.open(by_name["eng_sentences.tsv.bz2"], "rt", encoding="utf-8") as stream:
        for line in stream:
            sentence_id, _, sentence = line.rstrip("\n").split("\t", 2)
            english_id = int(sentence_id)
            if english_id not in links or not 8 <= len(sentence) <= 160:
                continue
            for chinese_id in sorted(links[english_id]):
                translated = chinese.get(chinese_id)
                if translated is None or not 2 <= len(translated) <= 100:
                    continue
                record = empty_record(
                    source_id,
                    f"eng-{english_id}:cmn-{chinese_id}",
                    sentence,
                )
                record["examples"] = [sentence]
                record["translations"] = {"zh-Hant": [translated]}
                yield record


def parse_ili_map(path: Path, source_id: str) -> Iterable[dict]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip() or line.startswith("#"):
                continue
            ili, pwn = line.rstrip("\n").split("\t")
            record = empty_record(source_id, pwn, pwn)
            record["senseRefs"] = [pwn]
            record["iliRefs"] = [ili]
            yield record


def bare_ipa(value: str) -> str:
    value = value.strip()
    if value.startswith(("/", "[")):
        closing = "/" if value[0] == "/" else "]"
        if (end := value.find(closing, 1)) > 1:
            return value[1:end].strip()
    return re.split(r"\s*~\s*", value, maxsplit=1)[0].strip(" /[]")


ARPABET_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ",
    "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "EH": "ɛ", "ER": "ɚ", "EY": "eɪ", "F": "f", "G": "g",
    "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ",
    "OY": "ɔɪ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}
ARPABET_VOWELS = {
    "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH",
    "IY", "OW", "OY", "UH", "UW",
}


def arpabet_to_ipa(value: str) -> str:
    phones = value.split()
    vowel_count = sum(re.sub(r"\d", "", phone) in ARPABET_VOWELS for phone in phones)
    output = ""
    syllable_start = 0
    for phone in phones:
        base = re.sub(r"\d", "", phone)
        if base not in ARPABET_IPA:
            raise SourceError(f"unsupported ARPABET phone: {phone}")
        stress = phone[-1] if phone[-1:].isdigit() else None
        if base in ARPABET_VOWELS:
            if stress in {"1", "2"} and vowel_count > 1:
                mark = "ˈ" if stress == "1" else "ˌ"
                output = output[:syllable_start] + mark + output[syllable_start:]
                syllable_start += 1
            output += "ə" if base == "AH" and stress == "0" else ARPABET_IPA[base]
            syllable_start = len(output)
        else:
            output += ARPABET_IPA[base]
    return output


def expression_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalized(value)).strip("-") or "expression"


def review_ipa(value: str) -> str:
    value = re.sub(r"[\s()]", "", bare_ipa(value))
    if value.startswith(("-", "–", "—")) or value.endswith(("-", "–", "—")):
        return ""
    return value


def reviewed_region(candidate: dict) -> str | None:
    region = candidate.get("region")
    tags = set(candidate.get("tags", []))
    if region in {"US", "General-American"} or "General-American" in tags:
        return "US"
    if region in {"UK", "Received-Pronunciation"} or "Received-Pronunciation" in tags:
        return "UK"
    return "General" if region in {None, "General"} else None


def review_pronunciations(
    expression: str,
    candidates: list[dict],
    cmudict: dict[str, list[dict]],
) -> tuple[list[dict], list[dict]]:
    priority = {"US": 0, "UK": 1, "General": 2}
    selected: list[tuple[str, str, str, dict]] = []
    seen: set[tuple[str, str]] = set()
    candidates = sorted(
        (
            item
            for item in candidates
            if item.get("notation") == "ipa"
            and reviewed_region(item) is not None
            and review_ipa(item.get("value", ""))
        ),
        key=lambda item: (
            priority[reviewed_region(item)],
            review_ipa(item["value"]),
            item.get("sourceRef", {}).get("sourceEntryRef", ""),
        ),
    )

    def select(candidate: dict) -> None:
        ipa = review_ipa(candidate["value"])
        region = reviewed_region(candidate)
        if (region, ipa) in seen:
            return
        seen.add((region, ipa))
        locale = "en-GB" if region == "UK" else "en-US"
        selected.append((ipa, locale, region, candidate.get("sourceRef", {})))

    for region in priority:
        candidate = next(
            (item for item in candidates if reviewed_region(item) == region),
            None,
        )
        if candidate is not None:
            select(candidate)
    for candidate in candidates:
        if len(selected) == 3:
            break
        select(candidate)

    words = re.findall(r"[a-z]+(?:'[a-z]+)?", normalized(expression))
    if len(words) == 1 and not any(region == "US" for _, _, region, _ in selected):
        values = cmudict.get(words[0], [])
        if values:
            value = values[0]
            ipa = arpabet_to_ipa(value["value"])
            if ("US", ipa) not in seen:
                selected.append((ipa, "en-US", "US", value.get("sourceRef", {})))
                selected.sort(key=lambda item: (priority[item[2]], item[0]))
                selected = selected[:3]

    if not selected:
        arpabet = next(
            (
                item
                for item in candidates
                if item.get("notation") == "arpabet" and item.get("value")
            ),
            None,
        )
        if arpabet:
            selected.append(
                (arpabet_to_ipa(arpabet["value"]), "en-US", "US", arpabet.get("sourceRef", {}))
            )

    if not selected:
        if not words or any(word not in cmudict for word in words):
            return [], []
        values = [cmudict[word][0] for word in words]
        selected.append(
            (
                " ".join(arpabet_to_ipa(value["value"]) for value in values),
                "en-US",
                "US",
                {},
            )
        )
        references = merged_list(
            value.get("sourceRef", {}) for value in values if value.get("sourceRef")
        )
    else:
        references = merged_list(
            reference for *_, reference in selected if reference
        )

    slug = expression_slug(expression)
    region_slug = {"US": "us", "UK": "gb", "General": "general"}
    pronunciations = [
        {
            "id": f"{slug}-{region_slug[region]}-{index}",
            "ipa": ipa,
            "speechLocale": locale,
            "region": region,
        }
        for index, (ipa, locale, region, _) in enumerate(selected, 1)
    ]
    return pronunciations, references


def canonical_part_of_speech(value: str | None) -> str:
    token = normalized(value or "")
    return {
        "n": "noun",
        "noun": "noun",
        "v": "verb",
        "verb": "verb",
        "a": "adjective",
        "s": "adjective",
        "adj": "adjective",
        "adjective": "adjective",
        "r": "adverb",
        "adv": "adverb",
        "adverb": "adverb",
        "prep": "preposition",
        "preposition": "preposition",
        "conj": "conjunction",
        "conjunction": "conjunction",
        "interj": "interjection",
        "interjection": "interjection",
        "pron": "pronoun",
        "pronoun": "pronoun",
        "det": "determiner",
        "determiner": "determiner",
    }.get(token, "phrase")


def review_senses(packet: dict) -> list[dict]:
    target_definition = normalized(packet.get("definition", ""))
    target_pos = canonical_part_of_speech(packet.get("partOfSpeech"))
    blocked_tags = {
        "archaic", "dated", "dialectal", "historical", "humorous", "obsolete",
        "rare", "uncommon",
    }
    candidates = [
        sense
        for sense in packet.get("candidateSenses", [])
        if isinstance(sense, dict)
        and sense.get("id")
        and sense.get("glosses")
        and not (blocked_tags & {normalized(tag) for tag in sense.get("tags", [])})
    ]
    candidates.sort(
        key=lambda sense: (
            0
            if target_definition
            in {normalized(gloss) for gloss in sense.get("glosses", [])}
            else 1,
            0 if canonical_part_of_speech(sense.get("partOfSpeech")) == target_pos else 1,
            0
            if sense.get("sourceRef", {}).get("sourceID", "").startswith("oewn")
            else 1,
            0 if sense.get("examples") else 1,
            sense["id"],
        )
    )
    exact = next(
        (
            sense
            for sense in candidates
            if target_definition
            in {normalized(gloss) for gloss in sense.get("glosses", [])}
        ),
        None,
    )
    if exact:
        candidates.remove(exact)
        primary = exact
        selected = [primary]
    else:
        fallback_pos = target_pos
        if fallback_pos == "phrase":
            fallback_pos = next(
                (
                    canonical_part_of_speech(sense.get("partOfSpeech"))
                    for sense in candidates
                    if canonical_part_of_speech(sense.get("partOfSpeech")) != "phrase"
                ),
                fallback_pos,
            )
        selected = [
            {
                "id": f"{packet['id']}-sense-1",
                "partOfSpeech": fallback_pos,
                "glosses": [packet.get("definition") or packet["target"]],
                "examples": [packet.get("example", "")],
                "tags": [],
                "sourceRef": next(iter(packet.get("sourceRefs", [])), {}),
            }
        ]

    used_meanings = {normalized(selected[0]["glosses"][0])}
    used_parts = {canonical_part_of_speech(selected[0].get("partOfSpeech"))}
    for candidate in sorted(
        (
            sense
            for sense in candidates
            if sense.get("sourceRef", {}).get("sourceID", "").startswith("oewn")
        ),
        key=lambda sense: (
            0 if canonical_part_of_speech(sense.get("partOfSpeech")) not in used_parts else 1,
            0
            if sense.get("sourceRef", {}).get("sourceID", "").startswith("oewn")
            else 1,
            0 if sense.get("examples") else 1,
            sense["id"],
        ),
    ):
        meaning = normalized(candidate["glosses"][0])
        part = canonical_part_of_speech(candidate.get("partOfSpeech"))
        if meaning in used_meanings or part in used_parts:
            continue
        selected.append(candidate)
        used_meanings.add(meaning)
        used_parts.add(part)
        if len(selected) == 2:
            break

    return [
        {
            "id": sense["id"],
            "partOfSpeech": canonical_part_of_speech(sense.get("partOfSpeech")),
            "meaning": sense["glosses"][0].strip(),
            "exampleCandidate": next(
                (
                    value.strip()
                    for value in sense.get("examples", [])
                    if isinstance(value, str)
                    and value.strip()
                    and contains_target_form(packet["target"], value)
                ),
                next(
                    (
                        value.strip()
                        for value in (packet.get("example", ""), *sense.get("examples", []))
                        if isinstance(value, str) and value.strip()
                    ),
                    "",
                ),
            ),
            "sourceRef": sense.get("sourceRef")
            or next(iter(packet.get("sourceRefs", [])), {}),
        }
        for sense in selected
    ]


def wiktextract_sense(word: str, part_of_speech: str | None, sense: dict) -> dict:
    glosses = [value.strip() for value in sense.get("glosses", []) if value.strip()]
    identity = next(iter(sense.get("senseid", [])), None)
    if identity is None:
        material = "|".join(
            (normalized(word), part_of_speech or "", glosses[0] if glosses else "")
        )
        identity = hashlib.sha256(material.encode()).hexdigest()[:16]
    translations: dict[str, list[str]] = {}
    for translation in sense.get("translations", []):
        code = translation.get("code")
        value = translation.get("word")
        if code and value and value.strip():
            translations.setdefault(code, []).append(value.strip())
    return {
        "id": identity,
        "partOfSpeech": part_of_speech,
        "glosses": glosses,
        "tags": sorted(set(sense.get("tags", []))),
        "examples": sorted(
            example["text"].strip()
            for example in sense.get("examples", [])
            if example.get("type", "example") == "example"
            and example.get("text", "").strip()
        ),
        "translations": {
            code: sorted(set(values), key=lambda value: (normalized(value), value))
            for code, values in sorted(translations.items())
        },
    }


def parse_wiktextract(path: Path, source_id: str) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            item = json.loads(line)
            if item.get("lang_code") != "en" or not item.get("word"):
                continue
            record = empty_record(
                source_id,
                f"{normalized(item['word'])}#{item.get('pos') or ''}#{line_number}",
                item["word"],
            )
            record["partOfSpeech"] = item.get("pos")
            record["pronunciations"] = [
                {
                    "notation": "ipa",
                    "value": bare_ipa(sound["ipa"]),
                    "speechLocale": (
                        "en-GB" if "UK" in sound.get("tags", []) else "en-US"
                    ),
                    "region": next(iter(sound.get("tags", [])), None),
                    "tags": sorted(sound.get("tags", [])),
                }
                for sound in item.get("sounds", [])
                if bare_ipa(sound.get("ipa", ""))
            ]
            record["senses"] = [
                wiktextract_sense(item["word"], item.get("pos"), sense)
                for sense in item.get("senses", [])
            ]
            record["definitions"] = [
                gloss for sense in record["senses"] for gloss in sense["glosses"]
            ]
            record["examples"] = [
                example for sense in record["senses"] for example in sense["examples"]
            ]
            record["senseRefs"] = [sense["id"] for sense in record["senses"]]
            for sense in record["senses"]:
                for language, values in sense["translations"].items():
                    record["translations"].setdefault(language, []).extend(values)
            for translation in item.get("translations", []):
                language = translation.get("code")
                value = translation.get("word")
                if language and value and value.strip():
                    record["translations"].setdefault(language, []).append(
                        value.strip()
                    )
            record["translations"] = {
                language: sorted(
                    set(values), key=lambda value: (normalized(value), value)
                )
                for language, values in sorted(record["translations"].items())
            }
            yield record


def snapshot_wiktextract(source_url: str, seed_path: Path, output: Path) -> dict:
    targets = {
        normalized(item["upgradedExpression"])
        for item in load_json(seed_path, list)
    }
    request = urllib.request.Request(
        source_url,
        headers={"User-Agent": "VocabyVocabularyBuilder/1.0"},
    )
    kept: list[bytes] = []
    try:
        with urllib.request.urlopen(request, timeout=60) as response, gzip.GzipFile(
            fileobj=response
        ) as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                try:
                    item = json.loads(raw_line)
                except json.JSONDecodeError as error:
                    raise SourceError(
                        f"invalid Wiktextract JSON at line {line_number}: {error}"
                    ) from error
                if (
                    item.get("lang_code") == "en"
                    and normalized(item.get("word", "")) in targets
                ):
                    kept.append(
                        json.dumps(
                            item,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                        + b"\n"
                    )
    except (OSError, urllib.error.URLError) as error:
        raise SourceError(f"cannot read Wiktextract source {source_url}: {error}") from error
    kept.sort()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=output.parent, delete=False) as destination:
        temporary = Path(destination.name)
        with gzip.GzipFile(fileobj=destination, mode="wb", mtime=0) as compressed:
            compressed.writelines(kept)
    os.replace(temporary, output)
    return {
        "path": str(output),
        "sha256": sha256(output),
        "bytes": output.stat().st_size,
        "records": len(kept),
    }


PARSERS = {
    "lemma_csv": parse_lemma_csv,
    "cmudict": parse_cmudict,
    "moby_pronunciator": parse_moby_pronunciator,
    "grundwortschatz_sqlite_gzip": parse_grundwortschatz_sqlite_gzip,
    "cow_tsv": parse_cow,
    "oewn_json_zip": parse_oewn,
    "cefr_j_xlsx_zip": parse_cefr_j,
    "freedict_tei_tar": parse_freedict,
    "gcide_tar": parse_gcide,
    "cedict_gzip": parse_cedict,
    "tatoeba_parallel_bz2": parse_tatoeba,
    "ili_map_tab": parse_ili_map,
    "wiktextract_jsonl_gz": parse_wiktextract,
}


def merged_list(values: Iterable[object]) -> list:
    unique = {
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")): value
        for value in values
    }
    return [unique[key] for key in sorted(unique)]


def merge_records(records: Iterable[dict]) -> list[dict]:
    merged: dict[tuple[str, str, str, str], dict] = {}
    for record in records:
        if not normalized(record["headword"]):
            continue
        key = (
            normalized(record["headword"]),
            normalized(record.get("partOfSpeech") or ""),
            normalized(record.get("cefr") or ""),
            normalized(record["sourceEntryRef"]),
        )
        if key not in merged:
            merged[key] = record
            continue
        current = merged[key]
        for field in (
            "definitions",
            "examples",
            "relatedTerms",
            "pronunciations",
            "senses",
            "forms",
            "senseRefs",
            "iliRefs",
        ):
            current[field] = merged_list([*current[field], *record[field]])
        for language, values in record["translations"].items():
            if isinstance(values, list):
                current["translations"][language] = sorted(
                    set(current["translations"].get(language, [])) | set(values),
                    key=lambda value: (normalized(value), value),
                )
    return sorted(merged.values(), key=lambda item: (
        normalized(item["headword"]),
        normalized(item.get("partOfSpeech") or ""),
        normalized(item.get("cefr") or ""),
        normalized(item["sourceEntryRef"]),
    ))


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def import_source(root: Path, source: dict, output: Path) -> int:
    path = verify_source(root, source)
    parser = PARSERS.get(source.get("adapter"))
    if parser is None:
        raise SourceError(f"{source['id']}: unknown adapter {source.get('adapter')}")
    if source.get("adapter") == "tatoeba_parallel_bz2":
        if not isinstance(path, list):
            raise SourceError(f"{source['id']}: Tatoeba adapter requires rawFiles")
        parsed = parser(path, source["id"])
    elif isinstance(path, list):
        raise SourceError(f"{source['id']}: adapter accepts only one raw file")
    elif source.get("adapter") == "lemma_csv":
        parsed = parser(path, source["id"], source.get("encoding", "utf-8-sig"))
    else:
        parsed = parser(path, source["id"])
    records = merge_records(parsed)
    content = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for record in records)
    atomic_write(output, content)
    return len(records)


def load_json(path: Path, expected: type) -> object:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SourceError(f"cannot read {path}: {error}") from error
    if not isinstance(value, expected):
        raise SourceError(f"{path} has the wrong JSON shape")
    return value


def read_jsonl(path: Path) -> list[dict]:
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as error:
        raise SourceError(f"cannot read {path}: {error}") from error


def part_of_speech_code(value: str | None) -> str:
    return {
        "noun": "n",
        "verb": "v",
        "adjective": "a",
        "adj": "a",
        "adverb": "r",
        "adv": "r",
        "s": "a",
    }.get(normalized(value or ""), normalized(value or "")[:1])


def translation_values(record: dict) -> list[str]:
    translations = record.get("translations", {})
    values = translations.get("zh-Hant") or translations.get("zh") or []
    if isinstance(values, str):
        values = [values]
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def source_reference(record: dict) -> dict:
    reference = {
        "sourceID": record["sourceID"],
        "sourceEntryRef": record["sourceEntryRef"],
    }
    if record.get("senseRefs"):
        reference["senseRefs"] = record["senseRefs"]
    return reference


def meaning_words(values: list[str]) -> set[str]:
    return {
        word
        for value in values
        for word in ENGLISH_WORD.findall(value.casefold())
        if word not in MEANING_STOP_WORDS
    }


SENTENCE_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")


def target_forms(target: str) -> set[str]:
    value = normalized(target)
    forms = {value}
    if " " in value:
        return forms
    forms.update({f"{value}s", f"{value}es", f"{value}ed", f"{value}ing"})
    if value.endswith("e"):
        forms.update({f"{value}d", f"{value[:-1]}ing"})
    if len(value) > 1 and value.endswith("y") and value[-2] not in "aeiou":
        forms.update({f"{value[:-1]}ies", f"{value[:-1]}ied"})
    if (
        len(value) > 2
        and value[-1] not in "aeiouy"
        and value[-2] in "aeiou"
        and value[-3] not in "aeiou"
    ):
        forms.update({f"{value}{value[-1]}ed", f"{value}{value[-1]}ing"})
    return forms


def contains_target_form(target: str, sentence: str) -> bool:
    return any(
        re.search(rf"(?<![a-z]){re.escape(form)}(?![a-z])", sentence.casefold())
        for form in target_forms(target)
    )


def definition_similarities(queries: dict[str, tuple[str, str]]) -> dict[str, float]:
    if not queries:
        return {}
    executable = shutil.which("xcrun")
    script = Path(__file__).with_name("definition_similarity.swift")
    if executable is None or not script.is_file():
        raise SourceError(
            "Xcode Swift and tools/definition_similarity.swift are required for sense review"
        )
    payload = "".join(
        json.dumps(
            {"id": key, "left": values[0], "right": values[1]},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for key, values in sorted(queries.items())
    )
    result = subprocess.run(
        [executable, "swift", str(script)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SourceError(f"definition similarity failed: {result.stderr.strip()}")
    try:
        scores = {
            item["id"]: float(item["distance"])
            for item in (
                json.loads(line) for line in result.stdout.splitlines() if line.strip()
            )
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SourceError(f"definition similarity returned invalid output: {error}") from error
    if set(scores) != set(queries):
        raise SourceError("definition similarity returned an incomplete result set")
    return scores


def similarity_key(record: dict, entry: dict) -> str:
    return "\u001f".join(
        (
            record["sourceEntryRef"],
            entry["reference"]["sourceEntryRef"],
            entry["value"],
        )
    )


def prepare_enrichment(
    input_dir: Path,
    existing_seed_path: Path,
    quotas: dict[str, int],
    output: Path,
    current_seed_path: Path | None = None,
    all_available: bool = False,
    approved_source_ids: set[str] | None = None,
) -> int:
    existing = load_json(existing_seed_path, list)
    current_seed = (
        load_json(current_seed_path, list) if current_seed_path is not None else None
    )
    current_keys = (
        {normalized(item["upgradedExpression"]) for item in current_seed}
        if current_seed is not None
        else None
    )
    excluded = (
        set()
        if current_seed is not None
        else {normalized(item["upgradedExpression"]) for item in existing}
    )
    records = [
        record
        for path in sorted(input_dir.glob("*.jsonl"))
        for record in read_jsonl(path)
    ]
    if approved_source_ids is not None:
        records = [
            record
            for record in records
            if record.get("sourceID") in approved_source_ids
        ]
    index_keys = None if all_available else current_keys
    senses_by_headword: dict[str, list[dict]] = {}
    pronunciations_by_headword: dict[str, list[dict]] = {}
    plain_expressions_by_headword: dict[str, set[str]] = {}
    validation_sources_by_headword: dict[str, set[str]] = {}
    for record in records:
        key = normalized(record.get("headword", ""))
        if not key or (index_keys is not None and key not in index_keys):
            continue
        source_ref = source_reference(record)
        senses = [
            {**sense, "sourceRef": source_ref}
            for sense in record.get("senses", [])
            if isinstance(sense, dict)
        ]
        if (
            record.get("sourceID", "").startswith("oewn")
            and record.get("definitions")
            and not senses
        ):
            senses = [
                {
                    "id": record["sourceEntryRef"],
                    "partOfSpeech": record.get("partOfSpeech"),
                    "glosses": record["definitions"],
                    "tags": [],
                    "examples": record.get("examples", []),
                    "translations": record.get("translations", {}),
                    "sourceRef": source_ref,
                }
            ]
        pronunciations = [
            {**pronunciation, "sourceRef": source_ref}
            for pronunciation in record.get("pronunciations", [])
            if isinstance(pronunciation, dict)
        ]
        if senses:
            senses_by_headword.setdefault(key, []).extend(senses)
        if pronunciations:
            pronunciations_by_headword.setdefault(key, []).extend(pronunciations)
        for value in record.get("relatedTerms", []):
            if not isinstance(value, str):
                continue
            value = value.replace("_", " ").strip()
            if (
                normalized(value) != key
                and ENGLISH_TERM.fullmatch(value)
                and len(value.split()) <= 8
            ):
                plain_expressions_by_headword.setdefault(key, set()).add(value)
        if senses or pronunciations:
            validation_sources_by_headword.setdefault(key, set()).add(
                record["sourceID"]
            )
    ili_by_pwn: dict[str, str] = {}
    ili_mapping_references: dict[str, dict] = {}
    for record in records:
        if "omw-ili" not in record.get("sourceID", "").casefold():
            continue
        for pwn in record.get("senseRefs", []):
            if record.get("iliRefs"):
                ili_by_pwn[pwn] = record["iliRefs"][0]
                ili_mapping_references[pwn] = source_reference(record)

    word_translation_records: list[tuple[dict, str]] = []
    sense_translation_records: list[tuple[str, dict, str, dict]] = []
    parallel_records: list[tuple[dict, str, str]] = []
    cefr_exact: dict[tuple[str, str], tuple[str, dict]] = {}
    cefr_any: dict[str, tuple[str, dict]] = {}

    def cefr_evidence_key(value: tuple[str, dict]) -> tuple:
        cefr, reference = value
        return (
            cefr,
            reference["sourceID"],
            reference["sourceEntryRef"],
            tuple(reference.get("senseRefs", [])),
        )

    lexical: list[dict] = []
    for record in records:
        key = normalized(record.get("headword", ""))
        if not key:
            continue
        values = translation_values(record)
        is_parallel = "tatoeba" in record.get("sourceID", "").casefold()
        if record.get("sourceID", "").casefold().startswith("cow"):
            cleaned = re.sub(r"\+的$", "", record["headword"]).replace("+", "")
            for pwn in record.get("senseRefs", []):
                ili = ili_by_pwn.get(pwn)
                mapping_reference = ili_mapping_references.get(pwn)
                if ili and mapping_reference:
                    sense_translation_records.append(
                        (ili, record, cleaned, mapping_reference)
                    )
        elif is_parallel and values and record.get("examples"):
            parallel_records.append((record, record["examples"][0], values[0]))
        elif values:
            word_translation_records.extend((record, value) for value in values)
        if record.get("cefr") in CEFR_LEVEL:
            value = (record["cefr"], source_reference(record))
            exact_key = (key, part_of_speech_code(record.get("partOfSpeech")))
            cefr_exact[exact_key] = min(
                cefr_exact.get(exact_key, value), value, key=cefr_evidence_key
            )
            cefr_any[key] = min(
                cefr_any.get(key, value), value, key=cefr_evidence_key
            )
        if (
            record.get("sourceID", "").startswith(("oewn", "grundwortschatz"))
            and record.get("definitions")
            and record.get("examples")
        ):
            lexical.append(record)

    converted_word_values = traditionalize([value for _, value in word_translation_records])
    translations: dict[str, list[dict]] = {}
    cedict_definitions_by_translation: dict[str, set[str]] = {}
    cedict_references_by_translation: dict[str, dict[tuple[str, str], dict]] = {}
    for (record, _), converted in zip(
        word_translation_records, converted_word_values, strict=True
    ):
        if "cedict" in record["sourceID"].casefold():
            cedict_definitions_by_translation.setdefault(converted, set()).update(
                record.get("definitions", [])
            )
            reference = source_reference(record)
            cedict_references_by_translation.setdefault(converted, {})[
                (reference["sourceID"], reference["sourceEntryRef"])
            ] = reference
        if (
            len(converted) < 2
            or len(converted) > 16
            or re.search(r"[A-Za-z]", converted)
        ):
            continue
        translations.setdefault(normalized(record["headword"]), []).append(
            {
                "value": converted,
                "reference": source_reference(record),
                "definitions": record.get("definitions", []),
                "sourceID": record["sourceID"],
                "partOfSpeech": part_of_speech_code(record.get("partOfSpeech")),
            }
        )

    converted_sense_values = traditionalize(
        [value for _, _, value, _ in sense_translation_records]
    )
    sense_translations: dict[str, list[dict]] = {}
    for (ili, record, _, mapping_reference), converted in zip(
        sense_translation_records, converted_sense_values, strict=True
    ):
        if (
            len(converted) < 1
            or len(converted) > 16
            or re.search(r"[A-Za-z0-9]", converted)
        ):
            continue
        sense_translations.setdefault(ili, []).append(
            {
                "value": converted,
                "reference": source_reference(record),
                "mappingReference": mapping_reference,
                "definitions": sorted(
                    cedict_definitions_by_translation.get(converted, set()),
                    key=lambda value: (normalized(value), value),
                ),
                "reviewReference": next(
                    iter(
                        sorted(
                            cedict_references_by_translation.get(converted, {}).values(),
                            key=lambda value: (
                                value["sourceID"],
                                value["sourceEntryRef"],
                            ),
                        )
                    ),
                    None,
                ),
                "sourceID": record["sourceID"],
            }
        )
    requires_sense_translation = bool(sense_translations)

    converted_parallel_values = traditionalize([value for _, _, value in parallel_records])
    translation_values_for_frequency = {
        entry["value"]
        for entries in sense_translations.values()
        for entry in entries
        if len(entry["value"]) <= 8
    }
    translation_usage: dict[str, int] = {}
    frequency_lengths = sorted({len(value) for value in translation_values_for_frequency})
    for sentence in converted_parallel_values:
        for length in frequency_lengths:
            for start in range(max(0, len(sentence) - length + 1)):
                value = sentence[start : start + length]
                if value in translation_values_for_frequency:
                    translation_usage[value] = translation_usage.get(value, 0) + 1

    parallel_by_word: dict[str, list[dict]] = {}
    for (record, sentence, _), converted in zip(
        parallel_records, converted_parallel_values, strict=True
    ):
        pair = {
            "sentence": sentence,
            "translation": converted,
            "reference": source_reference(record),
        }
        for word in set(SENTENCE_WORD.findall(sentence.casefold())):
            parallel_by_word.setdefault(word, []).append(pair)

    similarity_queries: dict[str, tuple[str, str]] = {}
    if requires_sense_translation:
        for record in lexical:
            target = record["headword"].replace("_", " ").strip()
            if (
                normalized(target) in excluded
                or ENGLISH_TERM.fullmatch(target) is None
                or not any(
                    isinstance(example, str)
                    and contains_target_form(target, example)
                    for example in record.get("examples", [])
                )
            ):
                continue
            left = " ".join(
                [*record.get("definitions", []), *record.get("relatedTerms", [])]
            )
            for ili in record.get("iliRefs", []):
                for entry in sense_translations.get(ili, []):
                    if entry["definitions"]:
                        similarity_queries[similarity_key(record, entry)] = (
                            left,
                            " ".join(entry["definitions"]),
                        )
    similarity_scores = definition_similarities(similarity_queries)

    candidates: dict[str, dict] = {}
    for record in lexical:
        target = record["headword"].replace("_", " ").strip()
        key = normalized(target)
        if key in excluded or not ENGLISH_TERM.fullmatch(target):
            continue
        definitions = [
            value.strip()
            for value in record["definitions"]
            if isinstance(value, str) and value.strip()
        ]
        examples = sorted(
            {
                value.strip()
                for value in record.get("examples", [])
                if isinstance(value, str)
                and value.strip()
                and contains_target_form(target, value)
                and len(value.strip()) <= 160
            },
            key=lambda value: (
                0 if 12 <= len(value) <= 100 else 1,
                len(value),
                normalized(value),
            ),
        )
        if not definitions or not examples or len(definitions[0]) > 220:
            continue

        pos = part_of_speech_code(record.get("partOfSpeech"))
        target_words = meaning_words(record.get("definitions", []))
        related_terms = [
            value.replace("_", " ").strip()
            for value in [target, *record.get("relatedTerms", [])]
            if isinstance(value, str) and value.strip()
        ]
        related_keys = {normalized(value) for value in related_terms}
        aligned_options = [
            {
                **entry,
                "termPriority": 0,
                "definitionMatch": len(
                    target_words & meaning_words(entry["definitions"])
                ),
                "synonymMatch": len(
                    (
                        {
                            normalized(value)
                            for value in entry["definitions"]
                            if isinstance(value, str)
                        }
                        & related_keys
                    )
                    - {key}
                ),
                "semanticDistance": similarity_scores.get(
                    similarity_key(record, entry), 2.0
                ),
            }
            for ili in record.get("iliRefs", [])
            for entry in sense_translations.get(ili, [])
        ]
        translation_options = sorted(
            [
                {
                    **entry,
                    "termPriority": priority,
                    "definitionMatch": len(
                        target_words & meaning_words(entry["definitions"])
                    ),
                    "synonymMatch": len(
                        (
                            {
                                normalized(value)
                                for value in entry["definitions"]
                                if isinstance(value, str)
                            }
                            & related_keys
                        )
                        - {key}
                    ),
                }
                for priority, term in enumerate(related_terms)
                for entry in translations.get(normalized(term), [])
            ],
            key=lambda item: (
                -item["definitionMatch"],
                -item["synonymMatch"],
                item["termPriority"],
                0 if "cedict" in item["sourceID"].casefold() else 1,
                -translation_usage.get(item["value"], 0),
                0 if 2 <= len(item["value"]) <= 6 else 1,
                abs(len(item["value"]) - 3),
                item["reference"]["sourceEntryRef"],
            ),
        )
        translation_options = [
            item
            for item in translation_options
            if (item["definitionMatch"] or item["synonymMatch"])
            and (
                not item["partOfSpeech"]
                or not pos
                or item["partOfSpeech"] == pos
            )
        ]
        cedict_options = [
            item
            for item in translation_options
            if "cedict" in item["sourceID"].casefold()
        ]
        if requires_sense_translation and aligned_options:
            translation_options = sorted(
                aligned_options,
                key=lambda item: (
                    item["semanticDistance"],
                    -item["definitionMatch"],
                    -item["synonymMatch"],
                    0
                    if pos == "a"
                    and item["value"].startswith(
                        ("有", "無", "不", "可", "非", "很", "易", "難")
                    )
                    else 1,
                    -len(item["definitions"]),
                    0 if translation_usage.get(item["value"], 0) else 1,
                    -translation_usage.get(item["value"], 0),
                    0 if 2 <= len(item["value"]) <= 6 else 1,
                    abs(len(item["value"]) - 3),
                    item["value"],
                    item["reference"]["sourceEntryRef"],
                ),
            )
        elif cedict_options:
            translation_options = cedict_options
        if not translation_options:
            continue

        cefr_entry = cefr_exact.get((key, pos)) or cefr_any.get(key)
        cefr = cefr_entry[0] if cefr_entry else "C1"
        level = CEFR_LEVEL[cefr]
        cefr_rank = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5}
        target_rank = cefr_rank[cefr]
        related_with_level = []
        for value in record.get("relatedTerms", []):
            if not isinstance(value, str):
                continue
            value = value.replace("_", " ").strip()
            if normalized(value) == key or not ENGLISH_TERM.fullmatch(value):
                continue
            related_cefr = cefr_exact.get((normalized(value), pos)) or cefr_any.get(normalized(value))
            if related_cefr and cefr_rank[related_cefr[0]] < target_rank:
                related_with_level.append((cefr_rank[related_cefr[0]], value, related_cefr[1]))
        related_with_level.sort(key=lambda value: (value[0], len(value[1]), normalized(value[1])))
        related = [value[1] for value in related_with_level]
        plain = related[0] if related else definitions[0]
        if normalized(plain) == key:
            continue

        first_word = SENTENCE_WORD.findall(key)[0]
        target_parallel = sorted(
            (
                pair
                for pair in parallel_by_word.get(first_word, [])
                if contains_target_form(target, pair["sentence"])
                and len(pair["sentence"]) <= 120
                and len(pair["translation"]) <= 80
            ),
            key=lambda pair: (
                0 if 12 <= len(pair["sentence"]) <= 90 else 1,
                len(pair["sentence"]),
                pair["reference"]["sourceEntryRef"],
            ),
        )[:250]
        parallel_matches = []
        target_terms = {
            word
            for form in target_forms(target)
            for word in SENTENCE_WORD.findall(form)
        }
        sense_words = meaning_words(definitions + record.get("relatedTerms", []))
        for pair in target_parallel:
            context_match = len(
                sense_words
                & (meaning_words([pair["sentence"]]) - target_terms)
            )
            if context_match == 0:
                continue
            for option_rank, option in enumerate(translation_options[:40]):
                if option["value"] in pair["translation"]:
                    parallel_matches.append(
                        (
                            0 if 12 <= len(pair["sentence"]) <= 90 else 1,
                            -context_match,
                            -option["definitionMatch"],
                            -option["synonymMatch"],
                            option["termPriority"],
                            len(pair["sentence"]),
                            pair["reference"]["sourceEntryRef"],
                            option["reference"]["sourceEntryRef"],
                            option_rank,
                            option,
                            pair,
                        )
                    )

        if parallel_matches:
            *_, translation_entry, parallel = min(parallel_matches)
            example = parallel["sentence"]
            example_translation = parallel["translation"]
            example_translation_mode = "parallel"
        else:
            translation_entry = translation_options[0]
            parallel = None
            example = examples[0]
            example_translation = None
            example_translation_mode = "usage-note"

        override = next(
            (
                SENSE_TRANSLATION_OVERRIDES[ili]
                for ili in record.get("iliRefs", [])
                if ili in SENSE_TRANSLATION_OVERRIDES
            ),
            None,
        )
        if override:
            translation_entry = {**translation_entry, "value": override}
            if example_translation and override not in example_translation:
                parallel = None
                example = examples[0]
                example_translation = None
                example_translation_mode = "usage-note"

        refs = [source_reference(record), translation_entry["reference"]]
        if translation_entry.get("mappingReference"):
            refs.append(translation_entry["mappingReference"])
        if translation_entry.get("reviewReference"):
            refs.append(translation_entry["reviewReference"])
        if cefr_entry:
            refs.append(cefr_entry[1])
        if related_with_level:
            refs.append(related_with_level[0][2])
        if parallel:
            refs.append(parallel["reference"])
        unique_refs = {
            (ref["sourceID"], ref["sourceEntryRef"]): ref for ref in refs
        }
        candidate = {
            "target": target,
            "plain": plain,
            "definition": definitions[0],
            "example": example,
            "exampleTranslationDraft": example_translation,
            "exampleTranslationMode": example_translation_mode,
            "translationDraft": translation_entry["value"],
            "partOfSpeech": pos,
            "cefr": cefr,
            "level": level,
            "sourceRefs": [unique_refs[value] for value in sorted(unique_refs)],
        }
        score = (
            0 if cefr_entry else 1,
            0 if parallel else 1,
            translation_entry.get("semanticDistance", 2.0),
            -translation_entry["definitionMatch"],
            -translation_entry["synonymMatch"],
            0 if related else 1,
            0 if len(target) <= 30 else 1,
            len(target),
            len(candidate["definition"]),
            normalized(target),
            record["sourceEntryRef"],
        )
        previous = candidates.get(key)
        if previous is None or score < previous["_score"]:
            candidate["_score"] = score
            candidates[key] = candidate

    selected: list[dict] = []
    if current_seed is not None:
        for current in sorted(
            current_seed,
            key=lambda item: (
                LEVEL_ORDER[item["level"]],
                item["sortOrder"],
                item["id"],
            ),
        ):
            key = normalized(current["upgradedExpression"])
            candidate = candidates.get(key)
            issues = []
            if candidate is None:
                meaning = current.get("meaning", {})
                example = current.get("example", {})
                candidate = {
                    "target": current["upgradedExpression"],
                    "plain": current["plainExpression"],
                    "definition": meaning.get("en", ""),
                    "example": example.get("text", ""),
                    "exampleTranslationDraft": example.get("translation", {}).get(
                        "zh-Hant"
                    ),
                    "exampleTranslationMode": "current-seed",
                    "translationDraft": meaning.get("zh-Hant", ""),
                    "partOfSpeech": "",
                    "cefr": {
                        "basic": "A2",
                        "intermediate": "B2",
                        "advanced": "C1",
                    }[current["level"]],
                    "level": current["level"],
                    "sourceRefs": [
                        {
                            "sourceID": "vocaby-original",
                            "sourceEntryRef": current["id"],
                        }
                    ],
                }
                issues.append("missing-aligned-lexical-candidate")
            packet = {
                key: value for key, value in candidate.items() if key != "_score"
            }
            packet["target"] = current["upgradedExpression"]
            packet["id"] = current["id"]
            if packet["level"] != current["level"]:
                issues.append("level-evidence-mismatch")
            packet["level"] = current["level"]
            packet["sortOrder"] = current["sortOrder"]
            packet["candidateSenses"] = merged_list(senses_by_headword.get(key, []))
            packet["candidatePronunciations"] = merged_list(
                pronunciations_by_headword.get(key, [])
            )
            packet["candidatePlainExpressions"] = sorted(
                plain_expressions_by_headword.get(key, set()),
                key=lambda value: (len(value.split()), len(value), normalized(value)),
            )
            packet["validationSourceIDs"] = sorted(
                validation_sources_by_headword.get(key, set())
            )
            if not packet["candidateSenses"]:
                issues.append("missing-structured-sense")
            if not packet["candidatePronunciations"]:
                issues.append("missing-pronunciation")
            packet["issues"] = sorted(issues)
            selected.append(packet)
        if all_available:
            used_ids = {item["id"] for item in current_seed}
            for level in LEVEL_ORDER:
                next_sort_order = max(
                    (
                        item["sortOrder"]
                        for item in current_seed
                        if item["level"] == level
                    ),
                    default=0,
                )
                numeric_ids = []
                for item in current_seed:
                    if item["level"] != level:
                        continue
                    match = re.fullmatch(rf"bank-{re.escape(level)}-(\d+)", item["id"])
                    if match:
                        numeric_ids.append(int(match.group(1)))
                next_id_number = max(numeric_ids, default=0)
                available = sorted(
                    (
                        item
                        for key, item in candidates.items()
                        if key not in current_keys and item["level"] == level
                    ),
                    key=lambda item: item["_score"],
                )
                for candidate in available:
                    item = {
                        key: value
                        for key, value in candidate.items()
                        if key != "_score"
                    }
                    next_sort_order += 1
                    next_id_number += 1
                    item["id"] = f"bank-{level}-{next_id_number:04d}"
                    while item["id"] in used_ids:
                        next_id_number += 1
                        item["id"] = f"bank-{level}-{next_id_number:04d}"
                    used_ids.add(item["id"])
                    item["sortOrder"] = next_sort_order
                    item["issues"] = []
                    selected.append(item)
    else:
        for level in LEVEL_ORDER:
            available = sorted(
                (item for item in candidates.values() if item["level"] == level),
                key=lambda item: item["_score"],
            )
            needed = quotas[level]
            if len(available) < needed:
                raise SourceError(
                    f"not enough {level} candidates: need {needed}, found {len(available)}"
                )
            for item in available[:needed]:
                item.pop("_score")
                selected.append(item)
    selected.sort(
        key=lambda item: (LEVEL_ORDER[item["level"]], normalized(item["target"]))
    )
    positions = {level: 0 for level in LEVEL_ORDER}
    for item in selected:
        level = item["level"]
        positions[level] += 1
        key = normalized(item["target"])
        if current_seed is None:
            item["id"] = f"bank-{level}-{positions[level]:04d}"
            item["sortOrder"] = positions[level]
        item["candidateSenses"] = merged_list(senses_by_headword.get(key, []))
        item["candidatePronunciations"] = merged_list(
            pronunciations_by_headword.get(key, [])
        )
        item["candidatePlainExpressions"] = sorted(
            plain_expressions_by_headword.get(key, set()),
            key=lambda value: (len(value.split()), len(value), normalized(value)),
        )
        item["validationSourceIDs"] = sorted(
            validation_sources_by_headword.get(key, set())
        )
        if current_seed is None:
            item["issues"] = []
    content = "".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for item in selected
    )
    atomic_write(output, content)
    return len(selected)


def traditionalize(values: list[str]) -> list[str]:
    executable = shutil.which("opencc")
    if executable is None:
        raise SourceError("OpenCC is required; install it with: brew install opencc")
    result = subprocess.run(
        [executable, "-c", "s2twp.json"],
        input=json.dumps(values, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SourceError(f"OpenCC failed: {result.stderr.strip()}")
    converted = json.loads(result.stdout)
    replacements = {
        "軟件": "軟體",
        "計算機": "電腦",
        "信息": "資訊",
        "網絡": "網路",
        "電腦程序": "電腦程式",
        "打印": "列印",
        "質量": "品質",
        "土著": "原住民",
        "上邊": "上方",
        "略稱": "縮寫",
    }
    return [apply_replacements(value, replacements) for value in converted]


def apply_replacements(value: str, replacements: dict[str, str]) -> str:
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def provenance_source(source: dict) -> dict:
    return {
        "id": source["id"],
        "owner": source.get("name", source["id"]),
        "sourceURL": source.get("canonicalURL"),
        "sourceVersion": source.get("version"),
        "retrievedAt": source.get("retrievedAt"),
        "licenses": [
            {
                "name": source.get("license", "Documented source terms"),
                "version": None,
                "url": source.get("licenseURL"),
                "evidence": source.get("licenseEvidence", []),
                "requiredNotice": source.get("requiredNotice"),
            }
        ],
        "attributionParties": [source.get("name", source["id"])],
        "attributionText": source.get("decision"),
        "rights": {key: "approved" for key in RIGHTS},
        "rightsReviewer": "codex-content-review-2026-07-15",
        "rightsVerifiedAt": "2026-07-15",
    }


def provenance_item(
    item_id: str,
    expression: str,
    level: str,
    cefr: str,
    source_refs: list[dict],
    origin: str,
) -> dict:
    difficulty = {"basic": 2, "intermediate": 5, "advanced": 8}[level]
    return {
        "itemID": item_id,
        "conceptKey": f"expression:{normalized(expression)}",
        "sourceIDs": sorted({ref["sourceID"] for ref in source_refs}),
        "sourceEntryRefs": source_refs,
        "origin": origin,
        "changesMade": "Selected, normalized, enriched for Taiwan learners, and formatted for Vocaby.",
        "cefr": cefr,
        "appLevel": level,
        "revision": 1,
        "difficulty": {
            "frequency": min(2, difficulty // 4),
            "transparency": min(2, difficulty // 4),
            "grammar": min(2, difficulty // 5),
            "register": min(2, difficulty // 5),
            "polysemy": min(2, difficulty // 4),
        },
        "taiwanUsefulness": 2,
        "englishReviewer": "codex-content-review-2026-07-11",
        "zhHantReviewer": "codex-content-review-2026-07-11",
        "levelReviewer": "codex-content-review-2026-07-11",
        "rightsReviewer": "codex-content-review-2026-07-11",
        "reviewedAt": "2026-07-11",
        "levelOverrideReason": None,
        "status": "approved",
    }


def build_reviewed(
    root: Path,
    manifest: dict,
    draft_path: Path,
    existing_seed_path: Path,
    seed_output: Path,
    provenance_output: Path,
    notices_output: Path,
) -> int:
    reviewed = read_jsonl(draft_path)
    load_json(existing_seed_path, list)
    if not reviewed:
        raise SourceError("reviewed bank is empty")
    catalog = {source["id"]: source for source in manifest["sources"]}
    owned_source = {
        "id": "vocaby-original",
        "owner": "Vocaby",
        "sourceURL": None,
        "sourceVersion": "project-owned",
        "retrievedAt": None,
        "licenses": [
            {
                "name": "Project-owned",
                "version": None,
                "url": None,
                "evidence": "repository-history",
                "requiredNotice": None,
            }
        ],
        "attributionParties": [],
        "attributionText": None,
        "rights": {key: "approved" for key in RIGHTS},
        "rightsReviewer": "codex-content-review-2026-07-15",
        "rightsVerifiedAt": "2026-07-15",
    }
    seed = []
    provenance_items = []
    used_source_ids: set[str] = set()
    uses_owned_source = False
    for item in reviewed:
        validate_reviewed_item(item)
        source_refs = merged_list(item["sourceRefs"])
        source_ids = sorted({reference["sourceID"] for reference in source_refs})
        validation_source_ids = sorted(set(item["validationSourceIDs"]))
        for source_id in source_ids:
            if source_id == "vocaby-original":
                uses_owned_source = True
                continue
            source = catalog.get(source_id)
            if source is None or source.get("appUse") != "approved":
                raise SourceError(f"source {source_id} is not approved for app use")
            used_source_ids.add(source_id)
        for source_id in validation_source_ids:
            if source_id == "vocaby-original":
                continue
            source = catalog.get(source_id)
            if source is None or source.get("appUse") != "approved":
                raise SourceError(
                    f"validation source {source_id} is not approved for app use"
                )
        seed.append({key: item[key] for key in SEED_KEYS})
        difficulty = {"basic": 2, "intermediate": 5, "advanced": 8}[
            item["level"]
        ]
        provenance_items.append(
            {
                "itemID": item["id"],
                "conceptKey": (
                    f"expression:{normalized(item['upgradedExpression'])}"
                    f"#sense:{item['primarySenseID']}"
                ),
                "sourceIDs": source_ids,
                "sourceEntryRefs": source_refs,
                "validationSourceIDs": validation_source_ids,
                "origin": "agent-reviewed",
                "changesMade": "Selected, sense-aligned, translated, reviewed, and formatted for Vocaby.",
                "cefr": item["cefr"],
                "appLevel": item["level"],
                "revision": 1,
                "difficulty": {
                    "frequency": min(2, difficulty // 4),
                    "transparency": min(2, difficulty // 4),
                    "grammar": min(2, difficulty // 5),
                    "register": min(2, difficulty // 5),
                    "polysemy": min(2, len(item["senses"]) - 1),
                },
                "taiwanUsefulness": 2,
                "englishReviewer": item["englishReviewer"],
                "zhHantReviewer": item["zhHantReviewer"],
                "levelReviewer": item.get(
                    "levelReviewer", item["englishReviewer"]
                ),
                "rightsReviewer": item.get(
                    "rightsReviewer", item["englishReviewer"]
                ),
                "reviewedAt": item.get("reviewedAt", "2026-07-15"),
                "levelOverrideReason": None,
                "status": item["reviewStatus"],
            }
        )
    seed.sort(
        key=lambda item: (
            LEVEL_ORDER[item["level"]],
            item["sortOrder"],
            item["id"],
        )
    )
    sources = [
        *([owned_source] if uses_owned_source else []),
        *(provenance_source(catalog[source_id]) for source_id in sorted(used_source_ids)),
    ]
    provenance = {
        "schemaVersion": 2,
        "bankVersion": "2026.07.5",
        "sources": sources,
        "items": provenance_items,
    }
    notice_lines = ["Vocaby Vocabulary Data Notices", ""]
    for source_id in sorted(used_source_ids):
        source = catalog[source_id]
        notice_lines.extend(
            [
                f"{source.get('name', source_id)} ({source.get('version', 'unknown version')})",
                f"Source: {source.get('canonicalURL', '')}",
                f"License: {source.get('license', 'Documented source terms')} {source.get('licenseURL', '')}".rstrip(),
                source.get("requiredNotice", ""),
                "Changes: selected, normalized, translated, sense-aligned, and adapted for Vocaby.",
                "",
            ]
        )
        for path in source.get("noticeFiles", []):
            try:
                notice = Path(root, path).read_text(encoding="utf-8")
            except OSError as error:
                raise SourceError(f"cannot read source notice {path}: {error}") from error
            notice = "\n".join(line.rstrip() for line in notice.splitlines())
            notice_lines.extend([re.sub(r"(?m)^={7,}$", "---", notice).rstrip(), ""])
    atomic_write(seed_output, json.dumps(seed, ensure_ascii=False, indent=2) + "\n")
    atomic_write(
        provenance_output,
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    atomic_write(notices_output, "\n".join(notice_lines).rstrip() + "\n")
    return len(seed)


def validate_seed_item(item: dict) -> None:
    required = (
        "id",
        "level",
        "sortOrder",
        "contentLanguageCode",
        "supportLanguageCodes",
        "plainExpression",
        "upgradedExpression",
        "primarySenseID",
        "pronunciations",
        "senses",
        "quiz",
    )
    if any(key not in item for key in required):
        raise SourceError(f"seed item {item.get('id', '<missing>')} is incomplete")
    if (
        item["level"] not in LEVEL_ORDER
        or item["contentLanguageCode"] != "en"
        or "zh-Hant" not in item["supportLanguageCodes"]
    ):
        raise SourceError(f"seed item {item['id']} has invalid language or level")
    if any(
        not isinstance(item[key], str) or not item[key].strip()
        for key in ("id", "plainExpression", "upgradedExpression")
    ):
        raise SourceError(f"seed item {item['id']} has missing required text")
    if len(item["plainExpression"].split()) > 8:
        raise SourceError(f"seed item {item['id']} plain expression is not concise")

    pronunciations = item["pronunciations"]
    senses = item["senses"]
    if not isinstance(pronunciations, list) or not pronunciations:
        raise SourceError(f"seed item {item['id']} requires pronunciations")
    if not isinstance(senses, list) or not 1 <= len(senses) <= 3:
        raise SourceError(f"seed item {item['id']} requires one to three senses")
    pronunciation_ids = [value.get("id") for value in pronunciations]
    if None in pronunciation_ids or len(set(pronunciation_ids)) != len(
        pronunciation_ids
    ):
        raise SourceError(f"seed item {item['id']} has duplicate pronunciation IDs")
    for pronunciation in pronunciations:
        if not all(
            isinstance(pronunciation.get(key), str)
            and pronunciation[key].strip()
            for key in ("id", "ipa", "speechLocale", "region")
        ):
            raise SourceError(f"seed item {item['id']} has malformed pronunciation")
        if (
            pronunciation["ipa"] != bare_ipa(pronunciation["ipa"])
            or not pronunciation["speechLocale"].startswith("en-")
        ):
            raise SourceError(f"seed item {item['id']} has malformed pronunciation")
        expected = {
            "US": ("us", "en-US"),
            "UK": ("gb", "en-GB"),
            "General": ("general", "en-US"),
        }.get(pronunciation["region"])
        if expected is None or pronunciation["speechLocale"] != expected[1] or not re.search(
            rf"-{expected[0]}-\d+$", pronunciation["id"]
        ):
            raise SourceError(f"seed item {item['id']} has inconsistent pronunciation region")

    sense_ids = [value.get("id") for value in senses]
    if (
        item["primarySenseID"] not in sense_ids
        or None in sense_ids
        or len(set(sense_ids)) != len(sense_ids)
    ):
        raise SourceError(f"seed item {item['id']} has invalid primary sense")
    for sense in senses:
        if sense.get("partOfSpeech") not in PARTS_OF_SPEECH:
            raise SourceError(f"seed item {item['id']} has unsupported part of speech")
        references = sense.get("pronunciationIDs")
        if (
            not isinstance(references, list)
            or not references
            or len(set(references)) != len(references)
            or any(value not in pronunciation_ids for value in references)
        ):
            raise SourceError(f"seed item {item['id']} references unknown pronunciation")
        meaning = sense.get("meaning", {})
        example = sense.get("example", {})
        translation = example.get("translation", {})
        texts = (
            meaning.get("en"),
            meaning.get("zh-Hant"),
            example.get("text"),
            translation.get("zh-Hant"),
        )
        if any(not isinstance(value, str) or not value.strip() for value in texts):
            raise SourceError(f"seed item {item['id']} has incomplete bilingual sense")
        if (
            translation["zh-Hant"].startswith(USAGE_NOTE_PREFIX)
            or re.search(r'[.!?]["’”)]?$', example["text"].strip()) is None
            or re.search(r'[。！？!?]["’”)]?$', translation["zh-Hant"].strip())
            is None
        ):
            raise SourceError(
                f"seed item {item['id']} requires a full-sentence translation"
            )

    quiz = item["quiz"] if isinstance(item["quiz"], dict) else {}
    prompt = quiz.get("prompt", {})
    options = quiz.get("options")
    correct = quiz.get("correctOptionIndex")
    if (
        not isinstance(prompt, dict)
        or any(
            not isinstance(prompt.get(language), str) or not prompt[language].strip()
            for language in ("en", "zh-Hant")
        )
        or not isinstance(options, list)
        or len(options) != 4
        or len({normalized(value) for value in options if isinstance(value, str)}) != 4
        or not isinstance(correct, int)
        or correct not in range(len(options))
        or options[correct] != item["upgradedExpression"]
    ):
        raise SourceError(f"seed item {item['id']} has invalid quiz")


def validate_reviewed_item(item: dict) -> None:
    validate_seed_item(item)
    required = (
        "sourceRefs",
        "validationSourceIDs",
        "cefr",
        "reviewStatus",
        "englishReviewer",
        "zhHantReviewer",
    )
    if any(key not in item for key in required):
        raise SourceError(f"review item {item.get('id', '<missing>')} is incomplete")
    if CEFR_LEVEL.get(item["cefr"]) != item["level"]:
        raise SourceError(f"review item {item['id']} has invalid language or level")
    if item["reviewStatus"] != "approved" or any(
        not isinstance(item[key], str) or not item[key].strip()
        for key in ("englishReviewer", "zhHantReviewer")
    ):
        raise SourceError(f"review item {item['id']} is not reviewed")
    if (
        not isinstance(item["sourceRefs"], list)
        or not item["sourceRefs"]
        or not isinstance(item["validationSourceIDs"], list)
    ):
        raise SourceError(f"review item {item['id']} has missing source evidence")


def audit_reviewed(path: Path, *, minimum_items: int = 5_000) -> dict:
    items = read_jsonl(path)
    if minimum_items < 1:
        raise SourceError("reviewed minimum must be positive")
    if len(items) < minimum_items:
        raise SourceError(
            f"reviewed bank must contain at least {minimum_items} items"
        )
    ids: set[str] = set()
    expressions: set[str] = set()
    levels = {level: 0 for level in LEVEL_ORDER}
    approved = 0
    for item in items:
        validate_reviewed_item(item)
        if item["id"] in ids:
            raise SourceError(f"duplicate review ID: {item['id']}")
        expression = normalized(item["upgradedExpression"])
        if expression in expressions:
            raise SourceError(
                f"duplicate reviewed expression: {item['upgradedExpression']}"
            )
        ids.add(item["id"])
        expressions.add(expression)
        levels[item["level"]] += 1
        approved += item["reviewStatus"] == "approved"
    return {"items": len(items), "levels": levels, "approved": approved}


REVIEW_INDEX_KEYS = {"schemaVersion", "shards"}
REVIEW_SHARD_KEYS = {
    "path",
    "items",
    "sha256",
    "firstID",
    "lastID",
    "cumulativeItems",
    "status",
    "final",
}


def load_review_index(index_path: Path, expected_count: int) -> list[dict]:
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SourceError(f"cannot read review index {index_path}: {error}") from error
    if (
        not isinstance(index, dict)
        or set(index) != REVIEW_INDEX_KEYS
        or index.get("schemaVersion") != 1
        or not isinstance(index.get("shards"), list)
    ):
        raise SourceError("review index has unknown or missing keys")
    if expected_count < 0:
        raise SourceError("expected review count cannot be negative")

    all_items = []
    ids = set()
    expressions = set()
    cumulative = 0
    checkpoint_number = 0
    baseline_seen = False
    for position, shard in enumerate(index["shards"]):
        if not isinstance(shard, dict) or set(shard) != REVIEW_SHARD_KEYS:
            raise SourceError("review shard index has unknown or missing keys")
        name = shard.get("path")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or Path(name).is_absolute()
        ):
            raise SourceError("review shard path must be a safe relative filename")
        checkpoint_match = re.fullmatch(r"checkpoint-(\d{4})\.jsonl", name)
        baseline_match = re.fullmatch(r"baseline-(\d+)\.jsonl", name)
        if checkpoint_match:
            checkpoint_number += 1
            if int(checkpoint_match.group(1)) != checkpoint_number:
                raise SourceError("review shard order does not match checkpoint numbers")
        elif baseline_match and position == 0 and not baseline_seen:
            baseline_seen = True
            if int(baseline_match.group(1)) != shard.get("items"):
                raise SourceError("baseline shard count does not match its path")
        else:
            raise SourceError("review shard path or order is invalid")
        if shard.get("status") != "approved" or not isinstance(shard.get("final"), bool):
            raise SourceError("review shard is not approved")
        if shard["final"] and position != len(index["shards"]) - 1:
            raise SourceError("final review shard must be last in order")
        item_count = shard.get("items")
        if (
            not isinstance(item_count, int)
            or item_count < 1
            or (
                checkpoint_match
                and not shard["final"]
                and item_count != 200
            )
            or (shard["final"] and item_count > 200)
        ):
            raise SourceError("non-final review checkpoints must contain exactly 200 items")
        shard_path = index_path.parent / name
        if not shard_path.is_file():
            raise SourceError(f"missing review shard: {name}")
        if sha256(shard_path) != shard.get("sha256"):
            raise SourceError(f"review shard hash mismatch: {name}")
        items = read_jsonl(shard_path)
        if len(items) != item_count:
            raise SourceError(f"review shard item count mismatch: {name}")
        if items[0].get("id") != shard.get("firstID") or items[-1].get("id") != shard.get("lastID"):
            raise SourceError(f"review shard first/last order mismatch: {name}")
        cumulative += len(items)
        if shard.get("cumulativeItems") != cumulative:
            raise SourceError(f"review shard cumulative count mismatch: {name}")
        for item in items:
            validate_reviewed_item(item)
            expression = normalized(item["upgradedExpression"])
            if item["id"] in ids or expression in expressions:
                raise SourceError("duplicate review ID or expression across shards")
            ids.add(item["id"])
            expressions.add(expression)
        all_items.extend(items)
    if cumulative != expected_count:
        raise SourceError(
            f"review index contains {cumulative} items, expected {expected_count}"
        )
    return all_items


def promote(
    root: Path,
    reviewed_path: Path,
    provenance_path: Path,
    notices_path: Path,
    output: Path,
) -> int:
    reviewed = load_json(reviewed_path, list)
    provenance = load_json(provenance_path, dict)
    try:
        notices = notices_path.read_text(encoding="utf-8")
    except OSError as error:
        raise SourceError(f"cannot read notices {notices_path}: {error}") from error
    source_manifest = load_manifest(root)
    external = {source["id"]: source for source in source_manifest["sources"]}
    sources = provenance.get("sources", [])
    source_ids = {source.get("id") for source in sources}
    if None in source_ids or len(source_ids) != len(sources):
        raise SourceError("provenance source IDs must be non-empty and unique")
    for source in sources:
        rights = source.get("rights", {})
        if any(rights.get(key) != "approved" for key in RIGHTS):
            raise SourceError(f"source {source.get('id', '<missing>')} rights are not approved")
        if source.get("id") in external and external[source["id"]].get("appUse") != "approved":
            raise SourceError(f"source {source['id']} is not approved for app use")
        for license_item in source.get("licenses", []):
            required_notice = license_item.get("requiredNotice")
            if required_notice and required_notice not in notices:
                raise SourceError(f"source {source['id']} required notice is missing")
    if not reviewed:
        raise SourceError("reviewed seed is empty")
    ids: set[str] = set()
    expressions: dict[str, str] = {}
    sort_orders: dict[str, list[int]] = {level: [] for level in LEVEL_ORDER}
    for item in reviewed:
        validate_seed_item(item)
        if item["id"] in ids:
            raise SourceError(f"duplicate seed ID: {item['id']}")
        ids.add(item["id"])
        expression = normalized(item["upgradedExpression"])
        if expression in expressions:
            raise SourceError(f"duplicate upgraded expression: {expressions[expression]} and {item['id']}")
        expressions[expression] = item["id"]
        sort_orders[item["level"]].append(item["sortOrder"])
    for level, values in sort_orders.items():
        if values and sorted(values) != list(range(1, len(values) + 1)):
            raise SourceError(f"{level} sortOrder must be contiguous from 1")
    provenance_items = provenance.get("items", [])
    by_id = {item.get("itemID"): item for item in provenance_items}
    if len(by_id) != len(provenance_items) or set(by_id) != ids:
        raise SourceError("seed and provenance IDs do not match")
    reviewed_by_id = {item["id"]: item for item in reviewed}
    concepts: set[str] = set()
    for item_id, item in by_id.items():
        required = ("conceptKey", "sourceIDs", "cefr", "appLevel", "englishReviewer", "zhHantReviewer", "levelReviewer", "rightsReviewer", "reviewedAt")
        if item.get("status") != "approved" or any(not item.get(key) for key in required):
            raise SourceError(f"provenance item {item_id} is not fully approved")
        if item["conceptKey"] in concepts:
            raise SourceError(f"duplicate concept key: {item['conceptKey']}")
        concepts.add(item["conceptKey"])
        if not isinstance(item["sourceIDs"], list) or any(
            source_id not in source_ids for source_id in item["sourceIDs"]
        ):
            raise SourceError(f"provenance item {item_id} uses an unknown source")
        validation_source_ids = item.get("validationSourceIDs")
        if not isinstance(validation_source_ids, list) or any(
            source_id != "vocaby-original"
            and (
                source_id not in external
                or external[source_id].get("appUse") != "approved"
            )
            for source_id in validation_source_ids
        ):
            raise SourceError(
                f"provenance item {item_id} uses a validation source "
                "that is not approved for app use"
            )
        if (
            CEFR_LEVEL.get(item["cefr"]) != item["appLevel"]
            or item["appLevel"] != reviewed_by_id[item_id]["level"]
        ):
            raise SourceError(f"provenance item {item_id} CEFR does not match app level")
    ordered = sorted(reviewed, key=lambda item: (LEVEL_ORDER[item["level"]], item["sortOrder"], item["id"]))
    atomic_write(output, json.dumps(ordered, ensure_ascii=False, indent=2) + "\n")
    return len(ordered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--source")
    import_parser = commands.add_parser("import-source")
    import_parser.add_argument("source")
    import_parser.add_argument("--output", type=Path)
    import_all_parser = commands.add_parser("import-all")
    import_all_parser.add_argument("--output-dir", type=Path)
    report_parser = commands.add_parser("report")
    report_parser.add_argument("--input-dir", type=Path)
    audit_parser = commands.add_parser("audit-reviewed")
    audit_parser.add_argument("--input", type=Path, required=True)
    audit_index_parser = commands.add_parser("audit-review-index")
    audit_index_parser.add_argument("--index", type=Path, required=True)
    audit_index_parser.add_argument("--expected-count", type=int, required=True)
    snapshot_parser = commands.add_parser("snapshot-wiktextract")
    snapshot_parser.add_argument("--source-url", required=True)
    snapshot_parser.add_argument("--seed", type=Path, required=True)
    snapshot_parser.add_argument("--output", type=Path, required=True)
    prepare_parser = commands.add_parser("prepare-enrichment")
    prepare_parser.add_argument("--input-dir", type=Path, required=True)
    prepare_parser.add_argument("--existing-seed", type=Path, required=True)
    prepare_parser.add_argument("--current-seed", type=Path)
    prepare_parser.add_argument("--all-available", action="store_true")
    prepare_parser.add_argument("--basic", type=int, default=950)
    prepare_parser.add_argument("--intermediate", type=int, default=1600)
    prepare_parser.add_argument("--advanced", type=int, default=2800)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_100k_parser = commands.add_parser("prepare-100k")
    prepare_100k_parser.add_argument("--input-dir", type=Path, required=True)
    prepare_100k_parser.add_argument("--retained", type=Path, required=True)
    prepare_100k_parser.add_argument("--output", type=Path, required=True)
    prepare_100k_parser.add_argument("--target-count", type=int, default=100_000)
    prepare_100k_parser.add_argument("--reserve-count", type=int, default=10_000)
    targets_parser = commands.add_parser("targets-to-seed")
    targets_parser.add_argument("--input", type=Path, required=True)
    targets_parser.add_argument("--output", type=Path, required=True)
    build_parser = commands.add_parser("build-reviewed")
    build_parser.add_argument("--input", type=Path, required=True)
    build_parser.add_argument("--existing-seed", type=Path, required=True)
    build_parser.add_argument("--seed-output", type=Path, required=True)
    build_parser.add_argument("--provenance-output", type=Path, required=True)
    build_parser.add_argument("--notices-output", type=Path, required=True)
    promote_parser = commands.add_parser("promote")
    promote_parser.add_argument("--reviewed", type=Path, required=True)
    promote_parser.add_argument("--provenance", type=Path, required=True)
    promote_parser.add_argument("--notices", type=Path, required=True)
    promote_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = load_manifest(root)

    if args.command == "audit-reviewed":
        print(
            json.dumps(
                audit_reviewed(args.input),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    elif args.command == "audit-review-index":
        items = load_review_index(args.index, args.expected_count)
        print(
            json.dumps(
                {"items": len(items), "approved": len(items)},
                sort_keys=True,
            )
        )
    elif args.command == "snapshot-wiktextract":
        print(
            json.dumps(
                snapshot_wiktextract(args.source_url, args.seed, args.output),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    elif args.command == "verify":
        sources = selected_sources(manifest, args.source)
        for source in sources:
            verify_source(root, source)
        project = root / "Vocaby.xcodeproj/project.pbxproj"
        if project.is_file() and "Content/Sources" in project.read_text(encoding="utf-8"):
            raise SourceError("Content/Sources must not be included in the Xcode project")
        print(f"verified {len(sources)} source(s)")
    elif args.command == "import-source":
        source = selected_sources(manifest, args.source)[0]
        output = args.output or root / f"Content/Sources/Imported/{source['id']}.jsonl"
        print(f"imported {import_source(root, source, output)} record(s) to {output}")
    elif args.command == "import-all":
        output_dir = args.output_dir or root / "Content/Sources/Imported"
        total = 0
        for source in manifest["sources"]:
            count = import_source(root, source, output_dir / f"{source['id']}.jsonl")
            total += count
            print(f"{source['id']}: {count}")
        print(f"imported {total} record(s)")
    elif args.command == "report":
        input_dir = args.input_dir or root / "Content/Sources/Imported"
        sources = []
        headwords: set[str] = set()
        total = 0
        for path in sorted(input_dir.glob("*.jsonl")):
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
            total += len(records)
            headwords.update(normalized(item["headword"]) for item in records)
            sources.append({"sourceID": path.stem, "records": len(records), "withCEFR": sum(bool(item.get("cefr")) for item in records), "withTraditionalChinese": sum(bool(item.get("translations", {}).get("zh-Hant")) for item in records)})
        report = {"summary": {"records": total, "uniqueHeadwords": len(headwords)}, "sources": sources}
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.command == "prepare-enrichment":
        quotas = {
            "basic": args.basic,
            "intermediate": args.intermediate,
            "advanced": args.advanced,
        }
        if any(value < 0 for value in quotas.values()):
            raise SourceError("level quotas cannot be negative")
        if args.all_available and args.current_seed is None:
            raise SourceError("--all-available requires --current-seed")
        approved_source_ids = {
            source["id"]
            for source in manifest["sources"]
            if source.get("appUse") == "approved"
        }
        count = prepare_enrichment(
            args.input_dir,
            args.existing_seed,
            quotas,
            args.output,
            args.current_seed,
            args.all_available,
            approved_source_ids,
        )
        print(f"prepared {count} enrichment candidate(s) to {args.output}")
    elif args.command == "prepare-100k":
        approved_source_ids = {
            source["id"]
            for source in manifest["sources"]
            if source.get("appUse") == "approved"
        }
        result = prepare_100k(
            args.input_dir,
            args.retained,
            args.output,
            approved_source_ids,
            target_count=args.target_count,
            reserve_count=args.reserve_count,
        )
        print(json.dumps(result, sort_keys=True))
    elif args.command == "targets-to-seed":
        count = targets_to_seed(args.input, args.output)
        print(f"wrote {count} Wiktextract target(s) to {args.output}")
    elif args.command == "build-reviewed":
        count = build_reviewed(
            root,
            manifest,
            args.input,
            args.existing_seed,
            args.seed_output,
            args.provenance_output,
            args.notices_output,
        )
        print(f"built {count} reviewed seed item(s)")
    else:
        print(
            f"promoted {promote(root, args.reviewed, args.provenance, args.notices, args.output)} item(s) to {args.output}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SourceError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
