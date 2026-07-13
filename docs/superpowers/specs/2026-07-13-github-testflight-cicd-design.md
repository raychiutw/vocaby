# GitHub CI/CD and TestFlight Design

**Date:** 2026-07-13

## Goal

Add GitHub Actions CI for every pull request and push to `main`, plus a manually triggered TestFlight deployment that the user or Codex can start with `gh`.

## Current Project Context

- The native project is `WordingDailyApp.xcodeproj` with the shared `WordingDailyApp` scheme.
- The scheme builds the app and widget, runs `WordingDailyAppTests`, and archives the Release configuration.
- The app targets iOS 17 or later and currently builds with Xcode 26.6.
- The app bundle ID is `com.raychiutw.WordingDaily`.
- The widget bundle ID is `com.raychiutw.WordingDaily.Widget`.
- Both targets require the App Group `group.com.raychiutw.WordingDaily`.
- Automatic signing is enabled, but the repository does not contain a Development Team value.
- The repository has no existing GitHub Actions workflow, Fastlane setup, or App Store export configuration.

## Chosen Approach

Use GitHub-hosted `macos-26` runners, Xcode 26.6, Apple-native `xcodebuild`, and an App Store Connect team API key. Do not add Fastlane, Ruby setup, certificate repositories, or third-party signing actions.

This is the smallest setup that covers testing, automatic cloud signing, archiving, and uploading. Fastlane becomes useful only if the project later automates tester groups, beta metadata, processing waits, or multiple apps.

## Repository Changes

### `.github/workflows/ci.yml`

- Trigger on pull requests targeting `main` and pushes to `main`.
- Grant the workflow only `contents: read` permission.
- Run on `macos-26` with `DEVELOPER_DIR` set to `/Applications/Xcode_26.6.app/Contents/Developer`.
- Check out the repository using the official GitHub checkout action pinned to an immutable commit SHA.
- Run the Swift test suite with `xcodebuild test` on the latest available iPhone 17 Pro simulator.
- Disable code signing for simulator tests.
- Run all Python `tools/test_*.py` tests with the standard library `unittest` runner.
- Cancel an older CI run when a newer commit arrives for the same branch or pull request.
- Never access Apple credentials.

### `.github/workflows/testflight.yml`

- Trigger only with `workflow_dispatch`.
- Accept deployments only from the `main` branch.
- Grant only `contents: read` permission.
- Allow only one TestFlight deployment at a time and never cancel one already uploading.
- Use the same runner, Xcode, Swift tests, and Python tests as CI.
- Perform all tests before creating the temporary App Store Connect key file.
- Set `CURRENT_PROJECT_VERSION` to `${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}` so every workflow run and rerun has a unique build number.
- Archive the `WordingDailyApp` Release scheme for `generic/platform=iOS`.
- Pass the Development Team and App Store Connect authentication directly to `xcodebuild`; do not commit signing identities or provisioning profiles.
- Upload with `xcodebuild -exportArchive` and remove the temporary `.p8` file even if archive or upload fails.
- Do not enable `testFlightInternalTestingOnly`, keeping the build eligible for external TestFlight and a later App Store submission.

### `.github/ExportOptions.plist`

Commit a non-secret export configuration with:

- `method`: `app-store-connect`
- `destination`: `upload`
- `signingStyle`: `automatic`
- `manageAppVersionAndBuildNumber`: `false`
- `uploadSymbols`: `true`

The team defaults to the team used to create the archive, so the plist does not need a hard-coded Team ID.

## GitHub Configuration

Create a `testflight` GitHub environment containing:

| Type | Name | Purpose |
| --- | --- | --- |
| Variable | `APPLE_TEAM_ID` | Apple Developer Team ID passed as `DEVELOPMENT_TEAM` |
| Secret | `ASC_KEY_ID` | App Store Connect team API Key ID |
| Secret | `ASC_ISSUER_ID` | App Store Connect team API Issuer ID |
| Secret | `ASC_PRIVATE_KEY` | Complete contents of the downloaded `.p8` private key |

The workflow must fail before archiving with a clear message when any value is absent. It must not echo credentials, enable shell tracing, upload the private key as an artifact, or persist it outside `$RUNNER_TEMP`.

## One-Time Apple Configuration

Before the first successful deployment:

1. Accept the current Apple Developer and App Store Connect agreements.
2. Register explicit App IDs for `com.raychiutw.WordingDaily` and `com.raychiutw.WordingDaily.Widget`.
3. Register `group.com.raychiutw.WordingDaily` and associate it with both App IDs.
4. Create the Wording Daily app record in App Store Connect using `com.raychiutw.WordingDaily`.
5. Create a team App Store Connect API key with permission to upload builds and use cloud-managed signing. Store its values only in the GitHub `testflight` environment.

Automatic signing may create or refresh certificates and provisioning profiles, but it must not be relied on to invent the App Group relationship or App Store Connect app record.

## Manual and Codex Operation

The user can run the workflow from GitHub Actions or ask Codex to publish. Codex uses:

```bash
gh workflow run testflight.yml --ref main
```

Codex then finds the dispatched run, watches it to completion with `gh run watch --exit-status`, and reports the run URL and any failing test, signing, archive, upload, or App Store Connect processing error.

The workflow's success means Apple accepted the upload. TestFlight may still show the build as Processing afterward; tester assignment and external beta review remain App Store Connect operations.

## Error Handling

- A test failure prevents all signing and upload work.
- A non-`main` manual dispatch must not deploy.
- Missing GitHub environment values fail before a private key file is written.
- Shell scripts use fail-fast settings and preserve `xcodebuild`'s exit status.
- The temporary private key is deleted on every exit path.
- GitHub retains the workflow logs; no additional artifact storage is added initially.
- A failed upload is rerun as a new GitHub Actions attempt, producing a new build number.

## Verification

Before landing the workflows:

1. Parse both YAML files to catch syntax errors.
2. Validate `ExportOptions.plist` with `plutil -lint`.
3. Run the same Swift and Python tests locally.
4. Run `git diff --check`.
5. Push the workflow files to `main`, confirm GitHub recognizes both workflows, and verify the CI run.
6. After Apple and GitHub credentials are configured, trigger `testflight.yml` through `gh` and watch the first upload through completion.

## Out of Scope

- App Store production release or App Review submission
- Automatic internal or external tester-group management
- Beta metadata and release-note automation
- Waiting for TestFlight processing inside the workflow
- Fastlane, `match`, self-hosted runners, or manually managed signing certificates
- Changes to the app's runtime behavior or UI

## Official References

- [Apple: Distributing your app for beta testing and releases](https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases)
- [Apple: Upload builds](https://developer.apple.com/help/app-store-connect/manage-builds/upload-builds/)
- [Apple: Creating API keys for App Store Connect API](https://developer.apple.com/documentation/appstoreconnectapi/creating-api-keys-for-app-store-connect-api)
- [GitHub: Manually running a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/manually-run-a-workflow)
- [GitHub: Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
