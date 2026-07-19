# Vocabulary 1.1.0 TestFlight Release Implementation Plan

> **Superseded on 2026-07-20 for the current internal release:** vocabulary
> production paused after checkpoint 25. Version 1.1.0 ships the reviewed
> 18,603-entry JSON bank; the 100,000-entry SQLite design remains future work
> and checkpoint 26 has not started.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the exact 100,000-lesson SQLite App, release it as public version 1.1.0, push the final main branch, and confirm the corresponding GitHub Actions build reaches internal TestFlight beta readiness.

**Architecture:** Reuse the existing manual `testflight.yml`, App Store Connect API credentials, `GITHUB_RUN_ID` build-number policy, and `wait_for_testflight.rb` terminal-state check. Add no release system; update the native version surfaces, run content/App/bundle gates, fast-forward the reviewed implementation to `main`, dispatch with `gh`, and monitor the exact run.

**Tech Stack:** Git, GitHub CLI, GitHub Actions, Xcode 26.6, App Store Connect API, Ruby status helper, Python/Swift tests.

## Global Constraints

- Public version is `1.1.0` for App and widget.
- Local `CURRENT_PROJECT_VERSION` remains `1`; TestFlight archive uses `GITHUB_RUN_ID`.
- This is an internal TestFlight deployment, so do not create a `v1.1.0` tag.
- Deploy only a clean, pushed `main`.
- Upload success is insufficient; completion requires `processingState=VALID` and `internalBuildState=IN_BETA_TESTING`.
- Do not expose, print, copy, or persist App Store Connect secrets.
- Keep the existing TestFlight environment and manual dispatch.
- Do not mark the active goal complete until every acceptance criterion is evidenced.

---

## File Map

- `VERSION`: public version `1.1.0`.
- `CHANGELOG.md`: 100,000-lesson offline-bank release entry.
- `Vocaby.xcodeproj/project.pbxproj`: all four `MARKETING_VERSION` assignments set to `1.1.0`.
- `tools/test_github_workflows.py`: version parity, GITHUB_RUN_ID, and readiness-helper contract.
- `.github/workflows/testflight.yml`: existing manual release workflow; change only if verification exposes a real gap.
- `tools/wait_for_testflight.rb`: existing Apple terminal-state checker; change only if verification exposes a real gap.
- `docs/manual-verification.md`: final release evidence and real-device performance result.

---

### Task 1: Set and Test Version 1.1.0

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`
- Modify: `Vocaby.xcodeproj/project.pbxproj`
- Modify: `tools/test_github_workflows.py`

**Interfaces:**
- Produces one public version shared by VERSION, App, widget, workflow status lookup, and changelog.

- [ ] **Step 1: Make the version contract test expect 1.1.0**

Change the version assertion to:

```python
def test_public_version_matches_all_native_release_surfaces(self):
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    project = (ROOT / "Vocaby.xcodeproj/project.pbxproj").read_text(
        encoding="utf-8"
    )
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    self.assertEqual(version, "1.1.0")
    self.assertEqual(project.count("MARKETING_VERSION = 1.1.0;"), 4)
    self.assertEqual(project.count("CURRENT_PROJECT_VERSION = 1;"), 4)
    self.assertIn("## 1.1.0 - 2026-07-17", changelog)
```

- [ ] **Step 2: Verify RED**

```sh
python3 -B -m unittest \
  tools.test_github_workflows.GitHubWorkflowTests.test_public_version_matches_all_native_release_surfaces
```

Expected: failure because current version is 1.0.0.

- [ ] **Step 3: Update the release surfaces**

Set `VERSION` to `1.1.0`, replace all four Xcode
`MARKETING_VERSION = 1.0.0;` assignments with `1.1.0`, and prepend:

```markdown
## 1.1.0 - 2026-07-17

- Expand the reviewed offline vocabulary bank to 100,000 complete lessons.
- Preserve exact or reviewed inferred CEFR and verified pronunciation for every lesson.
- Load vocabulary from an indexed read-only SQLite resource while preserving local learning progress.
```

- [ ] **Step 4: Verify GREEN and commit**

```sh
python3 -B -m unittest tools.test_github_workflows
git add VERSION CHANGELOG.md Vocaby.xcodeproj/project.pbxproj \
  tools/test_github_workflows.py
git diff --cached --check
git commit -m "release: prepare Vocaby 1.1.0"
git push origin HEAD
```

---

### Task 2: Run the Complete Release Audit

**Files:**
- Modify only files required to correct a failing verified gate.

**Interfaces:**
- Produces fresh evidence for content, source, database, tests, Release build, bundle, version, and Git state.

- [ ] **Step 1: Verify source and reviewed content**

```sh
python3 -B tools/vocabulary_sources.py verify
python3 -B tools/vocabulary_sources.py audit-review-index \
  --index Content/Reviews/vocabulary-100k/index.json \
  --expected-count 100000
python3 -B tools/build_vocabulary_database.py \
  --index Content/Reviews/vocabulary-100k/index.json \
  --output /tmp/VocabularyContent-a.sqlite \
  --expected-count 100000
python3 -B tools/build_vocabulary_database.py \
  --index Content/Reviews/vocabulary-100k/index.json \
  --output /tmp/VocabularyContent-b.sqlite \
  --expected-count 100000
cmp /tmp/VocabularyContent-a.sqlite /tmp/VocabularyContent-b.sqlite
```

Expected: all sources verify, review count is exactly 100,000, and database files are byte-identical.

- [ ] **Step 2: Run every Python test**

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tools -p 'test_*.py'
```

Expected: exit 0 with zero failures/errors.

- [ ] **Step 3: Run every Swift test**

```sh
rm -rf /tmp/Vocaby-1.1.0-Tests
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath /tmp/Vocaby-1.1.0-Tests \
  CODE_SIGNING_ALLOWED=NO
```

Expected: `** TEST SUCCEEDED **`.

- [ ] **Step 4: Run a clean Release device build**

```sh
rm -rf /tmp/Vocaby-1.1.0-Release
xcodebuild build \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/Vocaby-1.1.0-Release \
  CODE_SIGNING_ALLOWED=NO
```

Expected: `** BUILD SUCCEEDED **`.

- [ ] **Step 5: Audit the built App**

```sh
app=/tmp/Vocaby-1.1.0-Release/Build/Products/Release-iphoneos/Vocaby.app
test -f "${app}/VocabularyContent.sqlite"
test -f "${app}/ThirdPartyNotices.txt"
test ! -e "${app}/VocabularySeed.json"
find "${app}" -type f | rg 'Sources|Reviews|Imported|Reports|source-manifest|VocabularyProvenance' \
  && exit 1 || true
plutil -p "${app}/Info.plist" | rg 'CFBundleShortVersionString|CFBundleVersion|ITSAppUsesNonExemptEncryption'
sqlite3 "${app}/VocabularyContent.sqlite" \
  'SELECT value FROM metadata WHERE key="itemCount";'
```

Expected: version 1.1.0, local build number 1, encryption exemption false, and itemCount 100000.

- [ ] **Step 6: Audit Git and release contracts**

```sh
ruby -c tools/wait_for_testflight.rb
plutil -lint Vocaby/Info.plist .github/ExportOptions.plist
git diff --check
git status --short --branch
git log -1 --oneline --decorate
```

Expected: valid Ruby/plists, no diff errors, and no uncommitted files.

---

### Task 3: Review and Fast-Forward the Implementation to Main

**Files:**
- No content edits; this is branch integration.

**Interfaces:**
- Consumes: fully verified implementation branch.
- Produces: clean `main` at the verified commit, pushed to `origin/main`.

- [ ] **Step 1: Re-check remote state**

```sh
git fetch origin
git status --short --branch
git log --oneline --decorate --graph -12
```

Expected: implementation branch clean and based on current `origin/main`.

- [ ] **Step 2: Fast-forward main**

From the primary checkout:

```sh
git switch main
git pull --ff-only origin main
git merge --ff-only feature/vocabulary-100k-testflight
git push origin main
```

If fast-forward is impossible, stop and review the new main commits before choosing a non-destructive merge. Do not reset or force-push.

- [ ] **Step 3: Verify pushed state**

```sh
git status --short --branch
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
git tag --points-at HEAD
```

Expected: clean `main...origin/main`, equal SHAs, and no new `v1.1.0` tag.

---

### Task 4: Dispatch and Monitor TestFlight

**Files:**
- No repository edits unless the workflow exposes a verified release defect.

**Interfaces:**
- Consumes: pushed `main`, GitHub `testflight` environment, App Store Connect credentials.
- Produces: one GitHub Actions run whose `GITHUB_RUN_ID` is the App build number and whose Apple state is beta-ready.

- [ ] **Step 1: Verify GitHub authority and workflow inputs**

```sh
gh auth status
gh workflow view testflight.yml --yaml
gh api repos/raychiutw/vocaby/environments/testflight/variables/APPLE_TEAM_ID
```

Expected: authenticated account has `repo` and `workflow` scopes, workflow is manual/main-only, and the environment variable lookup succeeds. Secret values are never queried or printed.

- [ ] **Step 2: Dispatch on main**

```sh
before="$(gh run list --workflow testflight.yml --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
gh workflow run testflight.yml --ref main -f runner=macos-26
run_id=""
for attempt in {1..30}; do
  candidate="$(gh run list --workflow testflight.yml --branch main --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')"
  if [[ -n "${candidate}" && "${candidate}" != "${before}" ]]; then
    run_id="${candidate}"
    break
  fi
  sleep 2
done
test -n "${run_id}"
printf 'TestFlight run: %s\n' "${run_id}"
```

- [ ] **Step 3: Watch the exact run**

```sh
gh run watch "${run_id}" --exit-status
gh run view "${run_id}" --json status,conclusion,headBranch,headSha,url,jobs
```

Expected: test and deploy jobs both conclude `success`.

- [ ] **Step 4: Verify Apple readiness and version/build identity**

```sh
gh run view "${run_id}" --log > "/tmp/vocaby-testflight-${run_id}.log"
rg "processingState=VALID" "/tmp/vocaby-testflight-${run_id}.log"
rg "internalBuildState=IN_BETA_TESTING" "/tmp/vocaby-testflight-${run_id}.log"
rg "1\.1\.0.*${run_id}|${run_id}.*1\.1\.0" "/tmp/vocaby-testflight-${run_id}.log"
```

Expected: the log identifies public version 1.1.0, build number equal to the exact run ID, processing state VALID, and internal build state IN_BETA_TESTING.

- [ ] **Step 5: Run the completion audit**

Match every design acceptance criterion to fresh evidence:

- reviewed index and SQLite count exactly 100,000;
- all source/content/database tests pass;
- Swift tests and Release build pass;
- bundle contents and performance/manual checks pass;
- original IDs and SwiftData progress compatibility pass;
- version surfaces are all 1.1.0;
- main and origin/main are identical and clean;
- exact GitHub run succeeds;
- exact Apple build is VALID and IN_BETA_TESTING.

Only after every item is evidenced may the active goal be marked complete.
