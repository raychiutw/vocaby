from pathlib import Path
import plistlib
import subprocess
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
        self.assertIn("default: macos-26", workflow)
        self.assertIn("- vocaby-testflight", workflow)
        self.assertEqual(workflow.count("runs-on: ${{ inputs.runner }}"), 2)
        self.assertIn(
            "inputs.runner == 'vocaby-testflight' && '/Applications/Xcode.app/Contents/Developer'",
            workflow,
        )
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
            'CURRENT_PROJECT_VERSION="$GITHUB_RUN_ID"',
            workflow,
        )
        self.assertIn("-allowProvisioningUpdates", workflow)
        self.assertIn("-exportOptionsPlist .github/ExportOptions.plist", workflow)
        self.assertIn("trap 'rm -f \"$key_path\"' EXIT", workflow)
        self.assertIn("tools/wait_for_testflight.rb", workflow)
        self.assertIn('--build-number "$GITHUB_RUN_ID"', workflow)
        self.assertNotIn("set -x", workflow)
        self.assertIn("brew install opencc", workflow)

    def test_testflight_status_checker_is_valid_ruby(self):
        script = ROOT / "tools/wait_for_testflight.rb"
        self.assertTrue(script.is_file(), "TestFlight status checker is missing")

        result = subprocess.run(
            ["ruby", "-c", str(script)],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Syntax OK", result.stdout)

        jwt_check = subprocess.run(
            [
                "ruby",
                "-Itools",
                "-ropenssl",
                "-rbase64",
                "-rjson",
                "-e",
                (
                    'require "wait_for_testflight"; '
                    'key = OpenSSL::PKey::EC.generate("prime256v1"); '
                    'token = TestFlightStatus.jwt(private_key_pem: key.to_pem, '
                    'key_id: "TESTKEY", issuer_id: "TESTISSUER", now: Time.at(1000)); '
                    'header, payload, signature = token.split("."); '
                    'pad = ->(value) { value + "=" * ((4 - value.length % 4) % 4) }; '
                    'raw = Base64.urlsafe_decode64(pad.call(signature)); '
                    'raise "signature length" unless raw.bytesize == 64; '
                    'r = OpenSSL::BN.new(raw[0, 32], 2); '
                    's = OpenSSL::BN.new(raw[32, 32], 2); '
                    'der = OpenSSL::ASN1::Sequence(['
                    'OpenSSL::ASN1::Integer(r), OpenSSL::ASN1::Integer(s)]).to_der; '
                    'digest = OpenSSL::Digest::SHA256.digest("#{header}.#{payload}"); '
                    'raise "signature verification" unless key.dsa_verify_asn1(digest, der); '
                    'claims = JSON.parse(Base64.urlsafe_decode64(pad.call(payload))); '
                    'raise "claims" unless claims == {"iss"=>"TESTISSUER", '
                    '"iat"=>995, "exp"=>2200, "aud"=>"appstoreconnect-v1"}'
                ),
            ],
            capture_output=True,
            check=False,
            cwd=ROOT,
            text=True,
        )

        self.assertEqual(jwt_check.returncode, 0, jwt_check.stderr)

    def test_app_declares_no_non_exempt_encryption(self):
        with (ROOT / "Vocaby/Info.plist").open("rb") as file:
            info = plistlib.load(file)

        self.assertIs(info.get("ITSAppUsesNonExemptEncryption"), False)

    def test_public_version_sources_are_consistent(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "2.0.0")

        project = (ROOT / "Vocaby.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
        self.assertEqual(project.count("MARKETING_VERSION = 2.0.0;"), 4)
        self.assertNotIn("MARKETING_VERSION = 1.0;", project)

        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## 1.1.0", changelog)

        instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## Versioning and Releases", instructions)
        self.assertIn("`vX.Y.Z`", instructions)

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
