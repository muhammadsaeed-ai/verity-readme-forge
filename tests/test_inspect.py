from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from readmeforge.errors import ReadmeForgeError
from readmeforge.inspect import inspect_repository


class InspectTests(unittest.TestCase):
    def write(self, root: Path, relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_reads_python_manifest_and_detects_signals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "pyproject.toml", '[project]\nname = "stellar-app"\ndescription = "Evidence-based sample"\nrequires-python = ">=3.10"\n[project.scripts]\nstellar = "stellar.cli:main"\n')
            self.write(root, "src/stellar/cli.py", "def main():\n    return 0\n")
            self.write(root, "tests/test_cli.py", "def test_ok():\n    assert True\n")
            self.write(root, "docs/design.md", "# Design\n")
            self.write(root, ".github/workflows/ci.yml", "name: CI\n")
            report = inspect_repository(root)
        self.assertEqual(report["project"]["name"], "stellar-app")
        self.assertEqual(report["project"]["description"], "Evidence-based sample")
        self.assertEqual(report["project"]["primary_language"], "Python")
        self.assertTrue(report["summary"]["has_tests"])
        self.assertTrue(report["summary"]["has_ci"])
        self.assertEqual(report["project"]["package_scripts"]["python"]["stellar"], "stellar.cli:main")
        self.assertEqual(report["install_commands"][0]["command"], "python -m pip install .")

    def test_detects_npm_scripts_and_lockfile_manager(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "package.json", json.dumps({
                "name": "web-app", "description": "A web product",
                "scripts": {"dev": "vite --host", "test": "vitest run"},
                "dependencies": {"vite": "1"}, "devDependencies": {"vitest": "1"},
            }))
            self.write(root, "pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
            self.write(root, "src/main.ts", "console.log('x')\n")
            report = inspect_repository(root)
        self.assertEqual(report["project"]["name"], "web-app")
        self.assertTrue(any(item["command"] == "pnpm install" for item in report["install_commands"]))
        self.assertTrue(any(item["command"] == "pnpm test" for item in report["test_commands"]))
        self.assertTrue(any(item["command"] == "pnpm run dev" for item in report["run_commands"]))

    def test_ignores_generated_paths_and_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, ".gitignore", "private.py\ncache-dir/\n")
            self.write(root, "main.py", "print('safe')\n")
            self.write(root, "private.py", "SECRET_MARKER\n")
            self.write(root, "cache-dir/ignored.py", "ignored\n")
            self.write(root, ".venv/lib/ghost.py", "ignored\n")
            self.write(root, "dist/generated.py", "ignored\n")
            report = inspect_repository(root)
        paths = {item["path"] for item in report["files"]}
        self.assertIn("main.py", paths)
        self.assertNotIn("private.py", paths)
        self.assertNotIn("cache-dir/ignored.py", paths)
        self.assertNotIn(".venv/lib/ghost.py", paths)
        self.assertNotIn("dist/generated.py", paths)

    def test_report_does_not_contain_source_text_or_absolute_root(self) -> None:
        secret = "MUST_NOT_LEAK_SOURCE_22940"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "app.py", f"SECRET = '{secret}'\n")
            report = inspect_repository(root)
            encoded = json.dumps(report)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(str(root), encoded)
        self.assertFalse(report["analysis"]["project_code_executed"])
        self.assertFalse(report["analysis"]["absolute_path_recorded"])

    def test_rejects_invalid_paths_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ReadmeForgeError):
                inspect_repository(root / "missing")
            with self.assertRaises(ReadmeForgeError):
                inspect_repository(root, max_files=0)
            file_path = self.write(root, "file.txt", "hello")
            with self.assertRaises(ReadmeForgeError):
                inspect_repository(file_path)

    def test_file_limit_error_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "a.txt", "a")
            self.write(root, "b.txt", "b")
            with self.assertRaisesRegex(ReadmeForgeError, "max-files"):
                inspect_repository(root, max_files=1)

    def test_file_order_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "z.py", "z = 1\n")
            self.write(root, "a.py", "a = 1\n")
            first = inspect_repository(root)
            second = inspect_repository(root)
        self.assertEqual(first["files"], second["files"])
        expected = sorted((item["path"] for item in first["files"]), key=str.casefold)
        self.assertEqual([item["path"] for item in first["files"]], expected)


if __name__ == "__main__":
    unittest.main()
