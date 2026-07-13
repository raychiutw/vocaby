# GitHub CI/CD and TestFlight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic GitHub CI and a manually dispatched, `gh`-triggerable TestFlight deployment for Vocaby.

**Architecture:** Keep CI and deployment in two GitHub Actions workflows so pull requests never receive Apple credentials. Both workflows use GitHub-hosted macOS 26 and Xcode 26.6; deployment uses Apple-native `xcodebuild` with automatic signing and a temporary App Store Connect team API key.

**Tech Stack:** GitHub Actions, macOS 26 runner, Xcode 26.6, `xcodebuild`, Python standard-library `unittest`, App Store Connect API key, GitHub CLI.

## Global Constraints

- Keep the existing native `Vocaby.xcodeproj` and shared `Vocaby` scheme.
- Keep the iOS 17 minimum deployment target.
- Preserve bundle IDs `com.raychiutw.Vocaby` and `com.raychiutw.Vocaby.Widget`.
- Preserve App Group `group.com.raychiutw.Vocaby` for the app and widget.
- Use GitHub-hosted `macos-26` and `/Applications/Xcode_26.6.app/Contents/Developer`.
- Use automatic signing with an App Store Connect team API key.
- Do not add Fastlane, Ruby setup, third-party signing actions, a certificate repository, or manually managed provisioning profiles.
- Never expose Apple credentials to pull-request CI.
- TestFlight deployment remains manual through `workflow_dispatch` and deploys only `main`.
- Do not enable `testFlightInternalTestingOnly`.

---

### Task 1: Add the pull-request and main-branch CI workflow

**Files:**
- Create: `tools/test_github_workflows.py`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: existing `Vocaby.xcodeproj`, `Vocaby` scheme, `VocabyTests`, and `tools/test_*.py` discovery convention.
- Produces: a secret-free `CI` workflow and a reusable configuration contract test that Task 2 extends.

- [ ] **Step 1: Write the failing CI workflow contract test**

Create `tools/test_github_workflows.py` with:

```python
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GitHubWorkflowTests(unittest.TestCase):
    def test_ci_workflow_is_scoped_and_pinned(self):
        path = ROOT / ".github/workflows/ci.yml"
        self.assertTrue(path.is_file(), "CI workflow is missing")

        workflow = path.read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("runs-on: macos-26", workflow)
        self.assertIn(
            "/Applications/Xcode_26.6.app/Contents/Developer",
            workflow,
        )
        self.assertRegex(workflow, r"actions/checkout@[0-9a-f]{40}")
        self.assertIn("CODE_SIGNING_ALLOWED=NO", workflow)
        self.assertIn(
            "python3 -m unittest discover -s tools -p 'test_*.py'",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test and verify RED**

Run:

```bash
python3 -m unittest tools.test_github_workflows
```

Expected: FAIL with `CI workflow is missing` because `.github/workflows/ci.yml` does not exist.

- [ ] **Step 3: Add the minimal CI workflow**

Create `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  DEVELOPER_DIR: /Applications/Xcode_26.6.app/Contents/Developer

jobs:
  test:
    runs-on: macos-26
    timeout-minutes: 30
    steps:
      - name: Check out repository
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0

      - name: Run Swift tests
        run: |
          set -euo pipefail
          xcodebuild -version
          xcodebuild test \
            -project Vocaby.xcodeproj \
            -scheme Vocaby \
            -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
            -derivedDataPath "$RUNNER_TEMP/DerivedData" \
            CODE_SIGNING_ALLOWED=NO

      - name: Run Python tests
        run: python3 -m unittest discover -s tools -p 'test_*.py'
```

- [ ] **Step 4: Run the contract test and verify GREEN**

Run:

```bash
python3 -m unittest tools.test_github_workflows
```

Expected: `Ran 1 test` and `OK`.

- [ ] **Step 5: Parse the workflow YAML**

Run:

```bash
ruby -e 'require "psych"; ARGV.each { |path| Psych.parse_file(path) }' \
  .github/workflows/ci.yml
```

Expected: exit status 0 with no YAML syntax error.

- [ ] **Step 6: Run the complete local test baseline**

Run:

```bash
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath "$TMPDIR/Vocaby-CI-Tests" \
  CODE_SIGNING_ALLOWED=NO
python3 -m unittest discover -s tools -p 'test_*.py'
```

Expected: all 104 Swift tests pass; all 63 Python tests pass.

- [ ] **Step 7: Validate and commit the CI workflow**

Run:

```bash
git diff --check
git add .github/workflows/ci.yml tools/test_github_workflows.py
git diff --cached --check
git commit -m "ci: add iOS test workflow"
```

Expected: one commit containing only the CI workflow and its contract test.

---

### Task 2: Add the manual TestFlight deployment

**Files:**
- Modify: `tools/test_github_workflows.py`
- Create: `.github/workflows/testflight.yml`
- Create: `.github/ExportOptions.plist`

**Interfaces:**
- Consumes: the test conventions established in Task 1 and GitHub environment values `APPLE_TEAM_ID`, `ASC_KEY_ID`, `ASC_ISSUER_ID`, and `ASC_PRIVATE_KEY`.
- Produces: a main-only, manually dispatched TestFlight workflow and a non-secret App Store export configuration.

- [ ] **Step 1: Extend the contract test for TestFlight and export settings**

Replace `tools/test_github_workflows.py` with:

```python
from pathlib import Path
import plistlib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GitHubWorkflowTests(unittest.TestCase):
    def test_ci_workflow_is_scoped_and_pinned(self):
        path = ROOT / ".github/workflows/ci.yml"
        self.assertTrue(path.is_file(), "CI workflow is missing")

        workflow = path.read_text(encoding="utf-8")
        self.assertIn("pull_request:", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("runs-on: macos-26", workflow)
        self.assertIn(
            "/Applications/Xcode_26.6.app/Contents/Developer",
            workflow,
        )
        self.assertRegex(workflow, r"actions/checkout@[0-9a-f]{40}")
        self.assertIn("CODE_SIGNING_ALLOWED=NO", workflow)
        self.assertIn(
            "python3 -m unittest discover -s tools -p 'test_*.py'",
            workflow,
        )

    def test_testflight_workflow_is_manual_main_only_and_secret_backed(self):
        path = ROOT / ".github/workflows/testflight.yml"
        self.assertTrue(path.is_file(), "TestFlight workflow is missing")

        workflow = path.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotRegex(workflow, r"(?m)^  (push|pull_request):")
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("needs: test", workflow)
        self.assertIn("environment: testflight", workflow)
        self.assertIn("vars.APPLE_TEAM_ID", workflow)
        self.assertIn("secrets.ASC_KEY_ID", workflow)
        self.assertIn("secrets.ASC_ISSUER_ID", workflow)
        self.assertIn("secrets.ASC_PRIVATE_KEY", workflow)
        self.assertIn(
            'CURRENT_PROJECT_VERSION="${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}"',
            workflow,
        )
        self.assertIn("-allowProvisioningUpdates", workflow)
        self.assertIn("-exportOptionsPlist .github/ExportOptions.plist", workflow)
        self.assertIn("trap 'rm -f \"$key_path\"' EXIT", workflow)
        self.assertNotIn("set -x", workflow)

    def test_export_options_upload_without_internal_only_lock(self):
        path = ROOT / ".github/ExportOptions.plist"
        self.assertTrue(path.is_file(), "Export options are missing")

        with path.open("rb") as file:
            options = plistlib.load(file)

        self.assertEqual(
            options,
            {
                "destination": "upload",
                "manageAppVersionAndBuildNumber": False,
                "method": "app-store-connect",
                "signingStyle": "automatic",
                "uploadSymbols": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the extended contract test and verify RED**

Run:

```bash
python3 -m unittest tools.test_github_workflows
```

Expected: the CI test passes; the TestFlight and export-option tests fail with `TestFlight workflow is missing` and `Export options are missing`.

- [ ] **Step 3: Add the App Store export configuration**

Create `.github/ExportOptions.plist` with:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>destination</key>
    <string>upload</string>
    <key>manageAppVersionAndBuildNumber</key>
    <false/>
    <key>method</key>
    <string>app-store-connect</string>
    <key>signingStyle</key>
    <string>automatic</string>
    <key>uploadSymbols</key>
    <true/>
</dict>
</plist>
```

- [ ] **Step 4: Add the manual TestFlight workflow**

Create `.github/workflows/testflight.yml` with:

```yaml
name: TestFlight

on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: vocaby-testflight
  cancel-in-progress: false

env:
  DEVELOPER_DIR: /Applications/Xcode_26.6.app/Contents/Developer

jobs:
  test:
    runs-on: macos-26
    timeout-minutes: 30
    steps:
      - name: Check out repository
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0

      - name: Run Swift tests
        run: |
          set -euo pipefail
          xcodebuild -version
          xcodebuild test \
            -project Vocaby.xcodeproj \
            -scheme Vocaby \
            -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
            -derivedDataPath "$RUNNER_TEMP/DerivedData" \
            CODE_SIGNING_ALLOWED=NO

      - name: Run Python tests
        run: python3 -m unittest discover -s tools -p 'test_*.py'

  deploy:
    if: github.ref == 'refs/heads/main'
    needs: test
    runs-on: macos-26
    timeout-minutes: 45
    environment: testflight
    env:
      APPLE_TEAM_ID: ${{ vars.APPLE_TEAM_ID }}
      ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
      ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
      ASC_PRIVATE_KEY: ${{ secrets.ASC_PRIVATE_KEY }}
    steps:
      - name: Check out repository
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0

      - name: Archive and upload to TestFlight
        run: |
          set -euo pipefail
          : "${APPLE_TEAM_ID:?Missing testflight variable APPLE_TEAM_ID}"
          : "${ASC_KEY_ID:?Missing testflight secret ASC_KEY_ID}"
          : "${ASC_ISSUER_ID:?Missing testflight secret ASC_ISSUER_ID}"
          : "${ASC_PRIVATE_KEY:?Missing testflight secret ASC_PRIVATE_KEY}"

          key_path="$RUNNER_TEMP/AuthKey_${ASC_KEY_ID}.p8"
          archive_path="$RUNNER_TEMP/Vocaby.xcarchive"
          trap 'rm -f "$key_path"' EXIT
          umask 077
          printf '%s\n' "$ASC_PRIVATE_KEY" > "$key_path"

          xcodebuild archive \
            -project Vocaby.xcodeproj \
            -scheme Vocaby \
            -configuration Release \
            -destination 'generic/platform=iOS' \
            -archivePath "$archive_path" \
            -derivedDataPath "$RUNNER_TEMP/ArchiveDerivedData" \
            -hideShellScriptEnvironment \
            -allowProvisioningUpdates \
            -authenticationKeyPath "$key_path" \
            -authenticationKeyID "$ASC_KEY_ID" \
            -authenticationKeyIssuerID "$ASC_ISSUER_ID" \
            DEVELOPMENT_TEAM="$APPLE_TEAM_ID" \
            CURRENT_PROJECT_VERSION="${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}"

          xcodebuild -exportArchive \
            -archivePath "$archive_path" \
            -exportPath "$RUNNER_TEMP/TestFlightExport" \
            -exportOptionsPlist .github/ExportOptions.plist \
            -allowProvisioningUpdates \
            -authenticationKeyPath "$key_path" \
            -authenticationKeyID "$ASC_KEY_ID" \
            -authenticationKeyIssuerID "$ASC_ISSUER_ID"
```

- [ ] **Step 5: Run the contract test and verify GREEN**

Run:

```bash
python3 -m unittest tools.test_github_workflows
```

Expected: `Ran 3 tests` and `OK`.

- [ ] **Step 6: Validate YAML and plist syntax**

Run:

```bash
ruby -e 'require "psych"; ARGV.each { |path| Psych.parse_file(path) }' \
  .github/workflows/ci.yml \
  .github/workflows/testflight.yml
plutil -lint .github/ExportOptions.plist
```

Expected: YAML parsing exits 0 and `plutil` prints `.github/ExportOptions.plist: OK`.

- [ ] **Step 7: Run the complete local regression suite**

Run:

```bash
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath "$TMPDIR/Vocaby-TestFlight-Tests" \
  CODE_SIGNING_ALLOWED=NO
python3 -m unittest discover -s tools -p 'test_*.py'
```

Expected: all 104 Swift tests pass; all 65 Python tests pass.

- [ ] **Step 8: Validate and commit the TestFlight workflow**

Run:

```bash
git diff --check
git add \
  .github/ExportOptions.plist \
  .github/workflows/testflight.yml \
  tools/test_github_workflows.py
git diff --cached --check
git commit -m "ci: add manual TestFlight deployment"
```

Expected: one commit containing only the TestFlight workflow, export options, and extended contract test.

---

### Task 3: Configure GitHub, land the workflows, and run the first deployment

**Files:**
- No repository file changes.
- External configuration: Apple Developer, App Store Connect, GitHub environment `testflight`.

**Interfaces:**
- Consumes: `.github/workflows/ci.yml`, `.github/workflows/testflight.yml`, `.github/ExportOptions.plist`, an Apple Developer Team ID, and an App Store Connect team API key.
- Produces: a verified remote CI run and a monitored TestFlight upload initiated through `gh`.

- [ ] **Step 1: Verify the one-time Apple identifiers and app record**

In Apple Developer and App Store Connect, verify all of the following exact records exist before setting GitHub secrets:

```text
App ID:    com.raychiutw.Vocaby
Widget ID: com.raychiutw.Vocaby.Widget
App Group: group.com.raychiutw.Vocaby
App record bundle ID: com.raychiutw.Vocaby
```

Expected: both App IDs are associated with the App Group; current agreements are accepted; the App Store Connect app record exists; a team API key with upload and cloud-managed signing access has been downloaded once as a `.p8` file.

- [ ] **Step 2: Create the GitHub TestFlight environment**

Run:

```bash
gh api \
  --method PUT \
  repos/raychiutw/vocaby/environments/testflight
```

Expected: GitHub returns an environment response containing `"name":"testflight"`.

- [ ] **Step 3: Store the Team ID and App Store Connect key without printing secrets**

Run interactively from a trusted local shell:

```bash
printf 'Apple Team ID: '
IFS= read -r APPLE_TEAM_ID
gh variable set APPLE_TEAM_ID --env testflight --body "$APPLE_TEAM_ID"

printf 'App Store Connect Key ID: '
IFS= read -r ASC_KEY_ID
printf '%s' "$ASC_KEY_ID" | gh secret set ASC_KEY_ID --env testflight

printf 'App Store Connect Issuer ID: '
IFS= read -r ASC_ISSUER_ID
printf '%s' "$ASC_ISSUER_ID" | gh secret set ASC_ISSUER_ID --env testflight

printf 'Path to the App Store Connect .p8 key: '
IFS= read -r ASC_PRIVATE_KEY_PATH
gh secret set ASC_PRIVATE_KEY --env testflight < "$ASC_PRIVATE_KEY_PATH"

unset APPLE_TEAM_ID ASC_KEY_ID ASC_ISSUER_ID ASC_PRIVATE_KEY_PATH
```

Expected: every `gh` command succeeds and no secret value is printed.

- [ ] **Step 4: Verify only the environment value names**

Run:

```bash
gh variable list --env testflight
gh secret list --env testflight
```

Expected: variable `APPLE_TEAM_ID` and secrets `ASC_KEY_ID`, `ASC_ISSUER_ID`, and `ASC_PRIVATE_KEY` are listed.

- [ ] **Step 5: Land the implementation commits on `main` and push**

From the formal checkout after the implementation branch has been reviewed and merged, run:

```bash
git switch main
git status --short --branch
git push origin main
```

Expected: `main` pushes successfully and the working tree remains clean.

- [ ] **Step 6: Watch the CI run for the landed commit**

Run:

```bash
head_sha=$(git rev-parse HEAD)
run_id=$(gh run list \
  --workflow ci.yml \
  --commit "$head_sha" \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')
test -n "$run_id"
gh run watch "$run_id" --exit-status
```

Expected: the `CI` run finishes successfully.

- [ ] **Step 7: Dispatch TestFlight through `gh` and watch it**

Run:

```bash
started_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
gh workflow run testflight.yml --ref main

run_id=""
for _ in {1..12}; do
  run_id=$(gh run list \
    --workflow testflight.yml \
    --branch main \
    --event workflow_dispatch \
    --created ">=$started_at" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId')
  [[ -n "$run_id" ]] && break
  sleep 5
done

test -n "$run_id"
gh run watch "$run_id" --exit-status
gh run view "$run_id" --json url,status,conclusion,headSha
```

Expected: tests pass, Xcode archives both the app and widget with automatic signing, App Store Connect accepts the upload, and `gh run view` reports `conclusion: success` with the run URL.

- [ ] **Step 8: Verify App Store Connect received the build**

Open Vocaby in App Store Connect and inspect TestFlight build uploads.

Expected: version `1.0` appears with the build number represented by `${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}` in Processing or Complete state. Processing is an Apple-side state after upload success and is not a workflow failure.
