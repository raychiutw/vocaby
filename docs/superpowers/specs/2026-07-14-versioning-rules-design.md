# Vocaby Versioning Rules Design

## Goal

Adopt a small, explicit native iOS versioning policy starting at `1.0.0`, while allowing repeated TestFlight uploads without changing the public version.

## Version Policy

- `1.0.0` to `1.0.1`: bug fixes, small visual changes, and App Icon updates.
- `1.0.0` to `1.1.0`: new backward-compatible functionality.
- Major versions increase only for breaking changes after `1.0.0`.
- Formal releases use a `vX.Y.Z` Git tag.

## Version Sources

- Add a root `VERSION` file containing the current public version.
- Keep the app and widget Debug and Release `MARKETING_VERSION` values in `Vocaby.xcodeproj/project.pbxproj` equal to `VERSION`.
- Record each formal release at the top of `CHANGELOG.md`.
- Document the policy and release checklist in `AGENTS.md`.
- Vocaby is a native iOS project, so no `pubspec.yaml` is added.

For a formal release, update `VERSION`, every app and widget `MARKETING_VERSION`, and `CHANGELOG.md` in the release commit, then create the matching `vX.Y.Z` tag.

## TestFlight Builds

The manual `.github/workflows/testflight.yml` workflow overrides `CURRENT_PROJECT_VERSION` with `GITHUB_RUN_ID`. This gives every workflow run a unique numeric build number while allowing multiple TestFlight builds to share the same public version, such as `1.0.0`.

The repository's checked-in `CURRENT_PROJECT_VERSION` remains `1` for local builds. TestFlight overrides it only during archive creation.

## Initial State

This change establishes public version `1.0.0`, creates the version files and policy, and updates TestFlight build numbering. It does not create `v1.0.0`; that tag is created when `1.0.0` is formally released.

## Verification

- Confirm `VERSION` contains exactly `1.0.0`.
- Confirm all app and widget Debug and Release `MARKETING_VERSION` values are `1.0.0`.
- Confirm the TestFlight archive command passes `CURRENT_PROJECT_VERSION="$GITHUB_RUN_ID"`.
- Confirm `CHANGELOG.md` starts with the `1.0.0` entry.
- Run the repository's relevant tests, validate the workflow syntax, and run `git diff --check`.

## Scope Boundaries

- No automatic version-bump script.
- No workflow that commits or creates tags.
- No changes to App Store release or submission behavior.
