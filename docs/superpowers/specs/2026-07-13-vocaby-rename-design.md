# Vocaby Rename Design

## Goal

Rename the entire product and repository to **Vocaby**, including user-facing copy, internal code, folders, filenames, documentation, signing identifiers, and external project resources.

## Names and Identifiers

- App display name: `Vocaby`
- Product, target, scheme, module, and test names: `Vocaby`, `VocabyWidget`, and `VocabyTests`
- Xcode project: `Vocaby.xcodeproj`
- Main bundle ID: `com.raychiutw.Vocaby`
- Widget bundle ID: `com.raychiutw.Vocaby.Widget`
- App Group: `group.com.raychiutw.Vocaby`
- App Store Connect app name: `Vocaby`
- Local repository directory: `/Users/ray/Projects/vocaby`
- GitHub repository: `raychiutw/vocaby`

## Scope

- Rename the Xcode project, targets, schemes, modules, products, source directories, test directories, widget directory, Swift files, and matching Swift symbols.
- Rename every tracked file or directory whose name contains the former product name.
- Replace former product-name references in source code, resources, localization, tests, scripts, configuration, agent instructions, skills, and all documentation.
- Update the app and widget signing identifiers, App Group entitlements, notification identifiers, and persisted suite identifiers.
- Rename the local repository directory and GitHub repository.
- Install the existing test suite's OpenCC system dependency in GitHub Actions before Python tests run.
- Register the new identifiers under Apple Developer Team `8Z6WVFJ574`.
- Create the `Vocaby` App Store Connect record and continue the existing manual TestFlight workflow.
- Update tests and workflow contract checks for the new names and identifiers.

## Boundaries

- Git history is not rewritten; old names may remain in historical commits only.
- Existing identifiers owned by the read-only former Apple team are not deleted.
- No local data migration is required because the app has not shipped under the former identifiers.
- Do not add Fastlane or another deployment dependency.

## Verification

- Existing Swift and Python tests pass after identifier updates.
- GitHub CI passes on a clean hosted runner with OpenCC installed by the workflow.
- No tracked path, tracked file content, Xcode build setting, scheme, target, product, or Swift symbol retains the former product name.
- The repository works from `/Users/ray/Projects/vocaby`, and `origin` points to `raychiutw/vocaby`.
- The project archives with automatic signing for Team `8Z6WVFJ574`.
- GitHub environment variables and secrets are present without exposing secret values.
- A manually dispatched GitHub Actions run uploads a `Vocaby` build to TestFlight.
