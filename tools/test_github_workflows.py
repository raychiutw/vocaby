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
        self.assertIn("brew install opencc", workflow)

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
        self.assertIn("brew install opencc", workflow)

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
