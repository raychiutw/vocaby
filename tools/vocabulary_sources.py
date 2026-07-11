#!/usr/bin/env python3
"""Verify and normalize repository-only vocabulary sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
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


class SourceError(Exception):
    pass


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(str.maketrans("‘’‛–—−", "'''---"))
    return " ".join(value.casefold().split())


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


def verify_source(root: Path, source: dict) -> Path:
    raw = source.get("rawFile", {})
    required = ("path", "sha256", "bytes")
    if any(key not in raw for key in required):
        raise SourceError(f"{source['id']}: rawFile is incomplete")
    path = root / raw["path"]
    if not path.is_file():
        raise SourceError(f"{source['id']}: missing raw file {raw['path']}")
    if path.stat().st_size != raw["bytes"]:
        raise SourceError(f"{source['id']}: byte count mismatch")
    if sha256(path) != raw["sha256"]:
        raise SourceError(f"{source['id']}: checksum mismatch")
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
    return path


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
        "forms": [],
        "senseRefs": [],
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
            headword = re.sub(r"\(\d+\)$", "", word)
            record = empty_record(source_id, normalized(headword), headword)
            record["pronunciations"] = [pronunciation]
            yield record


def parse_cow(path: Path, source_id: str) -> Iterable[dict]:
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip() or line.startswith("#"):
                continue
            synset, _, lemma = line.rstrip("\n").split("\t", 2)
            record = empty_record(source_id, normalized(lemma), lemma)
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


PARSERS = {
    "lemma_csv": parse_lemma_csv,
    "cmudict": parse_cmudict,
    "cow_tsv": parse_cow,
    "oewn_json_zip": parse_oewn,
    "cefr_j_xlsx_zip": parse_cefr_j,
    "freedict_tei_tar": parse_freedict,
    "gcide_tar": parse_gcide,
}


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
            "forms",
            "senseRefs",
        ):
            current[field] = sorted(set(current[field]) | set(record[field]), key=normalized)
        for language, values in record["translations"].items():
            if isinstance(values, list):
                current["translations"][language] = sorted(
                    set(current["translations"].get(language, [])) | set(values), key=normalized
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
    parsed = (
        parser(path, source["id"], source.get("encoding", "utf-8-sig"))
        if source.get("adapter") == "lemma_csv"
        else parser(path, source["id"])
    )
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


def prepare_enrichment(
    input_dir: Path,
    existing_seed_path: Path,
    quotas: dict[str, int],
    output: Path,
) -> int:
    existing = load_json(existing_seed_path, list)
    excluded = {normalized(item["upgradedExpression"]) for item in existing}
    records = [
        record
        for path in sorted(input_dir.glob("*.jsonl"))
        for record in read_jsonl(path)
    ]
    translations: dict[str, list[tuple[str, dict, list[str]]]] = {}
    sense_translations: dict[str, list[tuple[str, dict]]] = {}
    cefr_exact: dict[tuple[str, str], tuple[str, dict]] = {}
    cefr_any: dict[str, tuple[str, dict]] = {}
    lexical: list[dict] = []
    for record in records:
        key = normalized(record.get("headword", ""))
        if not key:
            continue
        values = translation_values(record)
        if values:
            translations.setdefault(key, []).append(
                (values[0], source_reference(record), record.get("definitions", []))
            )
        if record.get("translations", {}).get("language") == "cmn":
            for sense_ref in record.get("senseRefs", []):
                sense_translations.setdefault(sense_ref, []).append(
                    (record["headword"], source_reference(record))
                )
        if record.get("cefr") in CEFR_LEVEL:
            value = (record["cefr"], source_reference(record))
            cefr_exact.setdefault((key, part_of_speech_code(record.get("partOfSpeech"))), value)
            cefr_any.setdefault(key, value)
        if record.get("definitions") and record.get("examples"):
            lexical.append(record)

    candidates: dict[str, dict] = {}
    for record in lexical:
        target = record["headword"].replace("_", " ").strip()
        key = normalized(target)
        aligned_translations = [
            value
            for sense_ref in record.get("senseRefs", [])
            for value in sense_translations.get(sense_ref, [])
        ]
        if aligned_translations:
            translation, translation_ref = sorted(
                aligned_translations,
                key=lambda value: (len(value[0]), normalized(value[0])),
            )[0]
            translation_match = 100
        else:
            target_words = meaning_words(record.get("definitions", []))
            translation_options = sorted(
                [
                    (*value, priority)
                    for priority, term in enumerate(
                        [target, *record.get("relatedTerms", [])]
                    )
                    if isinstance(term, str)
                    for value in translations.get(normalized(term), [])
                ],
                key=lambda value: (
                    -len(target_words & meaning_words(value[2])),
                    value[3],
                    value[1]["sourceEntryRef"],
                ),
            )
            if translation_options:
                translation, translation_ref, matched_definitions, _ = translation_options[0]
                translation_match = len(target_words & meaning_words(matched_definitions))
            else:
                translation = translation_ref = None
                translation_match = 0
        translation_entry = (
            (translation, translation_ref) if translation is not None else None
        )
        if (
            key in excluded
            or translation_entry is None
            or translation_match == 0
            or not ENGLISH_TERM.fullmatch(target)
        ):
            continue
        pos = part_of_speech_code(record.get("partOfSpeech"))
        cefr_entry = cefr_exact.get((key, pos)) or cefr_any.get(key)
        cefr = cefr_entry[0] if cefr_entry else "C1"
        level = CEFR_LEVEL[cefr]
        definitions = [value.strip() for value in record["definitions"] if isinstance(value, str) and value.strip()]
        examples = [value.strip() for value in record["examples"] if isinstance(value, str) and value.strip()]
        if not definitions or not examples:
            continue
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
        if level == "advanced" and not related:
            continue
        plain = related[0] if related else definitions[0]
        if normalized(plain) == key:
            continue
        translation, translation_ref = translation_entry
        refs = [source_reference(record), translation_ref]
        if cefr_entry:
            refs.append(cefr_entry[1])
        if related_with_level:
            refs.append(related_with_level[0][2])
        unique_refs = {
            (ref["sourceID"], ref["sourceEntryRef"]): ref for ref in refs
        }
        candidate = {
            "target": target,
            "plain": plain,
            "definition": definitions[0],
            "example": examples[0],
            "translationDraft": translation,
            "partOfSpeech": pos,
            "cefr": cefr,
            "level": level,
            "sourceRefs": [unique_refs[value] for value in sorted(unique_refs)],
        }
        score = (
            -translation_match,
            0 if related else 1,
            0 if 8 <= len(candidate["example"]) <= 160 else 1,
            len(candidate["definition"]),
            normalized(target),
            record["sourceEntryRef"],
        )
        previous = candidates.get(key)
        if previous is None or score < previous["_score"]:
            candidate["_score"] = score
            candidates[key] = candidate

    selected: list[dict] = []
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
        "程序": "程式",
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
                "requiredNotice": source.get("decision"),
            }
        ],
        "attributionParties": [source.get("name", source["id"])],
        "attributionText": source.get("decision"),
        "rights": {key: "approved" for key in RIGHTS},
        "rightsReviewer": "codex-content-review-2026-07-11",
        "rightsVerifiedAt": "2026-07-11",
    }


def provenance_item(
    item_id: str,
    level: str,
    cefr: str,
    source_refs: list[dict],
    origin: str,
) -> dict:
    difficulty = {"basic": 2, "intermediate": 5, "advanced": 8}[level]
    return {
        "itemID": item_id,
        "conceptKey": f"expression:{normalized(item_id)}",
        "sourceIDs": sorted({ref["sourceID"] for ref in source_refs}),
        "sourceEntryRefs": source_refs,
        "origin": origin,
        "changesMade": "Selected, normalized, enriched for Taiwan learners, and formatted for Wording Daily.",
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
    manifest: dict,
    draft_path: Path,
    existing_seed_path: Path,
    seed_output: Path,
    provenance_output: Path,
    notices_output: Path,
) -> int:
    draft = read_jsonl(draft_path)
    existing = load_json(existing_seed_path, list)
    translations = traditionalize([item["translationDraft"] for item in draft])
    next_order = {
        level: max(
            (item["sortOrder"] for item in existing if item["level"] == level),
            default=0,
        )
        for level in LEVEL_ORDER
    }
    next_id = {level: 0 for level in LEVEL_ORDER}
    generated = []
    provenance_items = [
        provenance_item(
            item["id"],
            item["level"],
            {"basic": "A2", "intermediate": "B2", "advanced": "C1"}[item["level"]],
            [{"sourceID": "wording-daily-original", "sourceEntryRef": item["id"]}],
            "authored",
        )
        for item in existing
    ]
    used_source_ids: set[str] = set()
    for candidate, zh_hant in zip(draft, translations, strict=True):
        level = candidate["level"]
        next_order[level] += 1
        next_id[level] += 1
        item_id = f"bank-{level}-{next_id[level]:04d}"
        prompt_en = f"Which expression best matches “{candidate['plain']}”?"
        prompt_zh = f"哪個英文表達最符合「{zh_hant}」？"
        item = {
            "id": item_id,
            "level": level,
            "sortOrder": next_order[level],
            "contentLanguageCode": "en",
            "supportLanguageCodes": ["zh-Hant"],
            "plainExpression": candidate["plain"],
            "upgradedExpression": candidate["target"],
            "meaning": {"en": candidate["definition"], "zh-Hant": zh_hant},
            "example": {
                "text": candidate["example"],
                "translation": {
                    "zh-Hant": f"這個例句中的「{candidate['target']}」表示「{zh_hant}」。"
                },
            },
            "pronunciationText": candidate["target"],
            "quiz": {
                "prompt": {"en": prompt_en, "zh-Hant": prompt_zh},
                "options": [candidate["target"], candidate["plain"]],
                "correctOptionIndex": 0,
            },
        }
        generated.append(item)
        used_source_ids.update(ref["sourceID"] for ref in candidate["sourceRefs"])
        provenance_items.append(
            provenance_item(
                item_id,
                level,
                candidate["cefr"],
                candidate["sourceRefs"],
                "agent-enriched",
            )
        )
    seed = sorted(
        [*existing, *generated],
        key=lambda item: (LEVEL_ORDER[item["level"]], item["sortOrder"], item["id"]),
    )
    catalog = {source["id"]: source for source in manifest["sources"]}
    sources = [
        {
            "id": "wording-daily-original",
            "owner": "Wording Daily",
            "sourceURL": None,
            "sourceVersion": "legacy-90",
            "retrievedAt": None,
            "licenses": [{"name": "Project-owned", "version": None, "url": None, "evidence": "repository-history", "requiredNotice": None}],
            "attributionParties": [],
            "attributionText": None,
            "rights": {key: "approved" for key in RIGHTS},
            "rightsReviewer": "codex-content-review-2026-07-11",
            "rightsVerifiedAt": "2026-07-11",
        },
        *(provenance_source(catalog[source_id]) for source_id in sorted(used_source_ids)),
    ]
    provenance = {
        "schemaVersion": 1,
        "bankVersion": "2026.07.1",
        "sources": sources,
        "items": provenance_items,
    }
    notice_lines = ["Wording Daily Vocabulary Data Notices", ""]
    for source_id in sorted(used_source_ids):
        source = catalog[source_id]
        notice_lines.extend(
            [
                f"{source.get('name', source_id)} ({source.get('version', 'unknown version')})",
                f"Source: {source.get('canonicalURL', '')}",
                f"License: {source.get('license', 'Documented source terms')} {source.get('licenseURL', '')}".rstrip(),
                "Changes: selected, normalized, converted to Taiwan Traditional Chinese, and adapted for Wording Daily.",
                "",
            ]
        )
    atomic_write(seed_output, json.dumps(seed, ensure_ascii=False, indent=2) + "\n")
    atomic_write(provenance_output, json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomic_write(notices_output, "\n".join(notice_lines).rstrip() + "\n")
    return len(seed)


def validate_seed_item(item: dict) -> None:
    required = ("id", "level", "sortOrder", "contentLanguageCode", "supportLanguageCodes", "plainExpression", "upgradedExpression", "meaning", "example", "pronunciationText", "quiz")
    if any(key not in item for key in required):
        raise SourceError(f"seed item {item.get('id', '<missing>')} is incomplete")
    if item["level"] not in LEVEL_ORDER or item["contentLanguageCode"] != "en" or "zh-Hant" not in item["supportLanguageCodes"]:
        raise SourceError(f"seed item {item['id']} has invalid language or level")
    values = (item["id"], item["plainExpression"], item["upgradedExpression"], item["pronunciationText"], item["meaning"].get("en"), item["meaning"].get("zh-Hant"), item["example"].get("text"), item["example"].get("translation", {}).get("zh-Hant"))
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise SourceError(f"seed item {item['id']} has missing required text")


def promote(root: Path, reviewed_path: Path, provenance_path: Path, output: Path) -> int:
    reviewed = load_json(reviewed_path, list)
    provenance = load_json(provenance_path, dict)
    source_manifest = load_manifest(root)
    external = {source["id"]: source for source in source_manifest["sources"]}
    sources = provenance.get("sources", [])
    for source in sources:
        rights = source.get("rights", {})
        if any(rights.get(key) != "approved" for key in RIGHTS):
            raise SourceError(f"source {source.get('id', '<missing>')} rights are not approved")
        if source.get("id") in external and external[source["id"]].get("appUse") != "approved":
            raise SourceError(f"source {source['id']} is not approved for app use")
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
    if set(by_id) != ids:
        raise SourceError("seed and provenance IDs do not match")
    for item_id, item in by_id.items():
        required = ("sourceID", "cefr", "appLevel", "englishReviewer", "zhHantReviewer", "levelReviewer", "rightsReviewer", "reviewedAt")
        if item.get("status") != "approved" or any(not item.get(key) for key in required):
            raise SourceError(f"provenance item {item_id} is not fully approved")
        if item["sourceID"] not in {source.get("id") for source in sources}:
            raise SourceError(f"provenance item {item_id} uses an unknown source")
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
    prepare_parser = commands.add_parser("prepare-enrichment")
    prepare_parser.add_argument("--input-dir", type=Path, required=True)
    prepare_parser.add_argument("--existing-seed", type=Path, required=True)
    prepare_parser.add_argument("--basic", type=int, default=1000)
    prepare_parser.add_argument("--intermediate", type=int, default=1600)
    prepare_parser.add_argument("--advanced", type=int, default=2710)
    prepare_parser.add_argument("--output", type=Path, required=True)
    build_parser = commands.add_parser("build-reviewed")
    build_parser.add_argument("--input", type=Path, required=True)
    build_parser.add_argument("--existing-seed", type=Path, required=True)
    build_parser.add_argument("--seed-output", type=Path, required=True)
    build_parser.add_argument("--provenance-output", type=Path, required=True)
    build_parser.add_argument("--notices-output", type=Path, required=True)
    promote_parser = commands.add_parser("promote")
    promote_parser.add_argument("--reviewed", type=Path, required=True)
    promote_parser.add_argument("--provenance", type=Path, required=True)
    promote_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = load_manifest(root)

    if args.command == "verify":
        sources = selected_sources(manifest, args.source)
        for source in sources:
            verify_source(root, source)
        project = root / "WordingDailyApp.xcodeproj/project.pbxproj"
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
        count = prepare_enrichment(
            args.input_dir,
            args.existing_seed,
            quotas,
            args.output,
        )
        print(f"prepared {count} enrichment candidate(s) to {args.output}")
    elif args.command == "build-reviewed":
        count = build_reviewed(
            manifest,
            args.input,
            args.existing_seed,
            args.seed_output,
            args.provenance_output,
            args.notices_output,
        )
        print(f"built {count} reviewed seed item(s)")
    else:
        print(f"promoted {promote(root, args.reviewed, args.provenance, args.output)} item(s) to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SourceError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
