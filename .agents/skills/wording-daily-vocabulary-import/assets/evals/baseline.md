# Baseline RED evidence

Before this skill and importer existed, the ten external files were downloaded
and checksummed manually. There was no manifest, no reusable command, no format
adapter registry, no deterministic JSONL, and no mechanical boundary preventing
candidate data from being treated as App content.

The first executable test run failed with:

```text
can't open file 'tools/vocabulary_sources.py': [Errno 2] No such file or directory
```

The user correction that exposed the process failure was: "利用一個個外部來源檔建立匯入詞庫的過程skill 與 重複執行程式".

The GREEN condition is one documented command path for every source, checksum
and license evidence validation before parsing, deterministic output, explicit
promotion gates, and proof that source folders are not in the Xcode project.
