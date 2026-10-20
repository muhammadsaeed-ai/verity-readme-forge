from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from readmeforge.inspect import inspect_repository
from readmeforge.render import render_json_report, render_readme, validate_report


class RenderTests(unittest.TestCase):
    def write(self, root: Path, relative: str, content: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_readme_includes_sections_and_architecture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "pyproject.toml", '[project]\nname = "sample-project"\ndescription = "Example description"\n')
            self.write(root, "src/sample/__init__.py", "__version__ = '1'\n")
            self.write(root, "tests/test_sample.py", "def test_ok():\n    assert 2 == 2\n")
            report = inspect_repository(root)
        readme = render_readme(report)
        for phrase in ("# sample-project", "## Installation", "## Usage", "## Testing", "~~~mermaid", "Contributing", "Security and limitations", "not a quality score"):
            self.assertIn(phrase, readme)
        self.assertIn("python -m pip install .", readme)

    def test_escapes_manifest_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "package.json", '{"name":"danger <img> | text","description":"line one\\nline two","scripts":{"test":"vitest"}}')
            report = inspect_repository(root)
        readme = render_readme(report)
        self.assertIn("&lt;img&gt;", readme)
        self.assertIn("\\|", readme)
        self.assertNotIn("<img>", readme)

    def test_json_report_is_valid_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "main.go", "package main\n")
            report = inspect_repository(root)
        output = render_json_report(report)
        self.assertEqual(output, render_json_report(report))
        self.assertEqual(json.loads(output)["schema_version"], 1)

    def test_schema_validation(self) -> None:
        with self.assertRaises(Exception):
            validate_report({"schema_version": 99})

    def test_structure_map_discloses_its_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "src/main.py", "x = 1\n")
            report = inspect_repository(root)
        self.assertIn("repository map, not a runtime dependency graph", render_readme(report))


if __name__ == "__main__":
    unittest.main()
