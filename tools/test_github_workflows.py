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
