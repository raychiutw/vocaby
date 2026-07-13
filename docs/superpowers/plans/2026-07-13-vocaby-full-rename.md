# Vocaby Full Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the complete product, repository, source tree, documentation, signing resources, and deployment pipeline to Vocaby, then upload the first build to TestFlight.

**Architecture:** Perform one mechanical, repository-wide rename guarded by a contract test that rejects every former-name spelling in tracked paths and content. Keep the native Xcode and GitHub Actions deployment architecture, adding only the OpenCC system package already required by the Python tools. Commit and verify local changes before renaming GitHub, the checkout directory, and Apple resources.

**Tech Stack:** SwiftUI, SwiftData, WidgetKit, Xcode 26.6, Python `unittest`, GitHub Actions, GitHub CLI, Apple Developer, App Store Connect

## Global Constraints

- App display name: `Vocaby`.
- Product, target, scheme, module, and test names: `Vocaby`, `VocabyWidget`, and `VocabyTests`.
- Main bundle ID: `com.raychiutw.Vocaby`.
- Widget bundle ID: `com.raychiutw.Vocaby.Widget`.
- App Group: `group.com.raychiutw.Vocaby`.
- Apple Developer Team: `8Z6WVFJ574`.
- Local repository directory: `/Users/ray/Projects/vocaby`.
- GitHub repository: `raychiutw/vocaby`.
- Do not rewrite git history, delete identifiers from the read-only former Apple team, add Fastlane, or add another deployment dependency.

---

### Task 1: Add a Complete-Rename Contract

**Files:**
- Create: `tools/test_vocaby_rename.py`

**Interfaces:**
- Consumes: the tracked file list and searchable tracked content from git.
- Produces: a repository contract that fails on former product names and missing canonical Vocaby paths.

- [ ] **Step 1: Write the failing contract test**

```python
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
LEGACY_PATTERN = r"wording[-_ ]?daily"


class VocabyRenameTests(unittest.TestCase):
    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
        )

    def test_tracked_paths_use_vocaby(self):
        result = self.git("ls-files")
        self.assertEqual(result.returncode, 0, result.stderr)
        legacy = [
            path for path in result.stdout.splitlines()
            if re.search(LEGACY_PATTERN, path, re.IGNORECASE)
        ]
        self.assertEqual(legacy, [])

        for path in (
            "Vocaby.xcodeproj/project.pbxproj",
            "Vocaby.xcodeproj/xcshareddata/xcschemes/Vocaby.xcscheme",
            "Vocaby/App/VocabyApp.swift",
            "Vocaby/Vocaby.entitlements",
            "VocabyTests",
            "VocabyWidget/VocabyWidget.swift",
            "VocabyWidget/VocabyWidget.entitlements",
            ".agents/skills/vocaby-vocabulary-import/SKILL.md",
        ):
            self.assertTrue((ROOT / path).exists(), path)

    def test_tracked_text_uses_vocaby(self):
        result = self.git("grep", "-Il", "-i", "-E", LEGACY_PATTERN, "--", ".")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertEqual(result.stdout.splitlines(), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract and observe the expected failure**

Run: `python3 -m unittest tools.test_vocaby_rename -v`

Expected: failures list the current Xcode project, source directories, skill directory, and tracked text containing the former name.

- [ ] **Step 3: Commit the failing contract with the rename implementation in Task 2**

Do not commit the red state separately; Task 2 makes this contract green in the same reviewable rename commit.

---

### Task 2: Rename Every Local Artifact and Reference

**Files:**
- Rename: `Vocaby.xcodeproj` to `Vocaby.xcodeproj`
- Rename: `Vocaby` to `Vocaby`
- Rename: `VocabyTests` to `VocabyTests`
- Rename: `VocabyWidget` to `VocabyWidget`
- Rename: `.agents/skills/vocaby-vocabulary-import` to `.agents/skills/vocaby-vocabulary-import`
- Rename: matching scheme, Swift entry-point, entitlements, and widget files to Vocaby names
- Modify: every tracked text file returned by the contract test

**Interfaces:**
- Consumes: the failing contract from Task 1 and all tracked repository content.
- Produces: the canonical Vocaby Xcode project, source tree, tests, skill, documentation, identifiers, URL scheme, notification names, and App Group names.

- [ ] **Step 1: Rename the top-level tracked paths**

```bash
git mv Vocaby.xcodeproj Vocaby.xcodeproj
git mv Vocaby Vocaby
git mv VocabyTests VocabyTests
git mv VocabyWidget VocabyWidget
git mv .agents/skills/vocaby-vocabulary-import .agents/skills/vocaby-vocabulary-import
git mv Vocaby.xcodeproj/xcshareddata/xcschemes/Vocaby.xcscheme Vocaby.xcodeproj/xcshareddata/xcschemes/Vocaby.xcscheme
git mv Vocaby/App/Vocaby.swift Vocaby/App/VocabyApp.swift
git mv Vocaby/Vocaby.entitlements Vocaby/Vocaby.entitlements
git mv VocabyWidget/VocabyWidget.swift VocabyWidget/VocabyWidget.swift
git mv VocabyWidget/VocabyWidget.entitlements VocabyWidget/VocabyWidget.entitlements
```

- [ ] **Step 2: Replace former-name spellings in tracked text**

Run the mechanical replacement in longest-name-first order:

```bash
git grep -Il -i -E 'wording[-_ ]?daily' -- . | while IFS= read -r file; do
  perl -pi -e 's/VocabyTests/VocabyTests/g; s/VocabyWidget/VocabyWidget/g; s/Vocaby/Vocaby/g; s/Vocaby/Vocaby/g; s/Vocaby/Vocaby/g; s/vocaby/vocaby/g; s/vocaby/vocaby/g' "$file"
done
```

The resulting entry-point names must be:

```swift
extension Notification.Name {
    static let vocabyInternalURL = Notification.Name("vocaby.internal-url")
}

final class VocabyAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate { }

@main
struct VocabyApp: App { }
```

The resulting widget family must use `VocabyWidgetEntry`, `VocabyWidgetProvider`, `VocabyWidgetView`, `VocabyWidget`, and `VocabyWidgetBundle`, with `vocaby://today` deep links.

- [ ] **Step 3: Verify Xcode names and identifiers**

Run: `xcodebuild -list -project Vocaby.xcodeproj`

Expected schemes and targets: `Vocaby`, `VocabyTests`, and `VocabyWidget`; no former names.

Run: `python3 -m unittest tools.test_vocaby_rename -v`

Expected: both rename contract tests pass.

- [ ] **Step 4: Run local regression tests**

```bash
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath /tmp/VocabyDerivedData \
  CODE_SIGNING_ALLOWED=NO
python3 -m unittest discover -s tools -p 'test_*.py'
```

Expected: all Swift and Python tests pass.

- [ ] **Step 5: Commit the full local rename**

```bash
git add -A
git diff --cached --check
git commit -m "refactor: rename app to Vocaby"
```

---

### Task 3: Make Hosted CI Self-Contained

**Files:**
- Modify: `tools/test_github_workflows.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/testflight.yml`

**Interfaces:**
- Consumes: the existing Python tools' `opencc` executable requirement.
- Produces: CI and TestFlight test jobs that install OpenCC before Python tests.

- [ ] **Step 1: Extend the workflow contract and observe failure**

Add these assertions for both workflow files:

```python
for name in ("ci.yml", "testflight.yml"):
    workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
    self.assertIn("brew install opencc", workflow)
```

Run: `python3 -m unittest tools.test_github_workflows -v`

Expected: failure because neither workflow installs OpenCC.

- [ ] **Step 2: Install OpenCC before Python tests in both workflows**

```yaml
      - name: Install OpenCC
        run: brew install opencc
```

Keep the existing pinned checkout action, Xcode path, permissions, manual TestFlight trigger, and secret handling unchanged.

- [ ] **Step 3: Verify workflows and full local tests**

```bash
python3 -m unittest tools.test_github_workflows -v
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml", aliases: true); YAML.load_file(".github/workflows/testflight.yml", aliases: true)'
plutil -lint .github/ExportOptions.plist
python3 -m unittest discover -s tools -p 'test_*.py'
```

Expected: all commands pass.

- [ ] **Step 4: Commit the CI fix**

```bash
git add .github/workflows/ci.yml .github/workflows/testflight.yml tools/test_github_workflows.py
git diff --cached --check
git commit -m "ci: install OpenCC for vocabulary tests"
```

---

### Task 4: Rename the GitHub Repository and Local Checkout

**Files:**
- Move: `/Users/ray/Projects/vocaby` to `/Users/ray/Projects/vocaby`
- Modify external resource: GitHub repository `raychiutw/vocaby` to `raychiutw/vocaby`
- Modify local git configuration: `origin`

**Interfaces:**
- Consumes: a clean, committed local Vocaby tree.
- Produces: the canonical local and GitHub repository names while preserving history, Actions, secrets, variables, and the `testflight` environment.

- [ ] **Step 1: Rename the GitHub repository**

```bash
gh api --method PATCH repos/raychiutw/vocaby -f name=vocaby
git remote set-url origin https://github.com/raychiutw/vocaby.git
```

- [ ] **Step 2: Push the committed rename**

Run: `git push origin main`

Expected: `main` pushes successfully to `raychiutw/vocaby`.

- [ ] **Step 3: Rename the local checkout directory**

```bash
test ! -e /Users/ray/Projects/vocaby
mv /Users/ray/Projects/vocaby /Users/ray/Projects/vocaby
```

- [ ] **Step 4: Verify repository identity and GitHub settings from the new path**

```bash
git -C /Users/ray/Projects/vocaby status --short --branch
git -C /Users/ray/Projects/vocaby remote -v
gh repo view raychiutw/vocaby --json nameWithOwner,defaultBranchRef
gh variable list --repo raychiutw/vocaby --env testflight
gh secret list --repo raychiutw/vocaby --env testflight
```

Expected: clean `main`, `origin` uses the Vocaby URL, the repository exists, `APPLE_TEAM_ID=8Z6WVFJ574`, and the environment is present.

---

### Task 5: Create Apple and App Store Connect Resources

**Files:**
- Create external identifiers: `com.raychiutw.Vocaby`, `com.raychiutw.Vocaby.Widget`, `group.com.raychiutw.Vocaby`
- Create external app record: `Vocaby`
- Configure GitHub environment: `testflight`

**Interfaces:**
- Consumes: Apple Team `8Z6WVFJ574`, the renamed Xcode project, and the existing GitHub TestFlight workflow.
- Produces: signing resources, App Store Connect API credentials, and GitHub environment secrets required by `xcodebuild` upload.

- [ ] **Step 1: Register the App Group and explicit App IDs**

In Apple Developer, create `group.com.raychiutw.Vocaby`, then create both explicit App IDs with App Groups enabled and associate the new group with both.

- [ ] **Step 2: Create the App Store Connect app record**

Create the iOS app named `Vocaby` using bundle ID `com.raychiutw.Vocaby`, version `1.0`, and SKU `vocaby-ios-20260713`.

- [ ] **Step 3: Create a team App Store Connect API key**

Create one team key named `Vocaby GitHub Actions` with the App Manager role. Download the `.p8` once to `/Users/ray/.config/vocaby/AuthKey.p8`, record its Key ID and Issuer ID, and never print its contents.

- [ ] **Step 4: Store credentials in the GitHub environment**

```bash
gh variable set APPLE_TEAM_ID --repo raychiutw/vocaby --env testflight --body '8Z6WVFJ574'
gh secret set ASC_KEY_ID --repo raychiutw/vocaby --env testflight
gh secret set ASC_ISSUER_ID --repo raychiutw/vocaby --env testflight
gh secret set ASC_PRIVATE_KEY --repo raychiutw/vocaby --env testflight < /Users/ray/.config/vocaby/AuthKey.p8
```

Expected: `gh variable list` shows the Team ID and `gh secret list` shows all three secret names without revealing their values.

---

### Task 6: Verify CI, Archive, and TestFlight Upload

**Files:**
- No planned source changes; failures are fixed at their root and committed before retrying.

**Interfaces:**
- Consumes: the renamed repository, green local tests, Apple resources, and GitHub environment credentials.
- Produces: green hosted CI and a processed Vocaby TestFlight build.

- [ ] **Step 1: Verify the push-triggered CI run**

```bash
ci_run_id="$(gh run list --repo raychiutw/vocaby --workflow ci.yml --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch --repo raychiutw/vocaby "$ci_run_id" --exit-status
```

Expected: Swift and Python tests pass on `macos-26`.

- [ ] **Step 2: Dispatch the manual TestFlight workflow**

```bash
gh workflow run testflight.yml --repo raychiutw/vocaby --ref main
testflight_run_id="$(gh run list --repo raychiutw/vocaby --workflow testflight.yml --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch --repo raychiutw/vocaby "$testflight_run_id" --exit-status
```

Expected: tests pass, the archive exports with automatic signing, and upload succeeds.

- [ ] **Step 3: Confirm processing in App Store Connect**

Verify the new build appears under Vocaby in TestFlight. Record the build number and processing status without enabling external testing or App Store release.

- [ ] **Step 4: Run the completion audit**

```bash
git -C /Users/ray/Projects/vocaby status --short --branch
git -C /Users/ray/Projects/vocaby ls-files | rg -i 'wording[-_ ]?daily|vocaby'
git -C /Users/ray/Projects/vocaby grep -Il -i -E 'wording[-_ ]?daily|vocaby' -- .
python3 -m unittest discover -s /Users/ray/Projects/vocaby/tools -p 'test_*.py'
```

Expected: clean synchronized `main`, both legacy-name searches produce no results, all tests pass, GitHub CI is green, and App Store Connect shows the uploaded Vocaby build.
