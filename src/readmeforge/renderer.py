"""Render a useful Markdown README from the repository facts that were actually observed."""

from __future__ import annotations

import json
import re
from typing import Any


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _code(value: object) -> str:
    text = str(value)
    fence = "````" if "```" in text else "```"
    return f"{fence}text\n{text}\n{fence}"


def render_readme(profile: dict[str, Any]) -> str:
    """Generate Markdown. Unobserved capabilities are never presented as implemented facts."""
    name = str(profile["name"])
    summary = str(profile["summary"]).rstrip(".") + "."
    repo_url = profile.get("repository_url")
    title_line = f"<p align=\"center\">\n  <img src=\"assets/readme/hero.svg\" alt=\"{name} documentation overview\" width=\"100%\" />\n</p>\n\n" if "assets/readme/hero.svg" in profile.get("project_tree", []) else ""
    lines = [
        title_line.rstrip(),
        f"# {name}",
        "",
        f"**{summary}**",
        "",
        "<p><sub>README drafted locally by <strong>VerityAgent ReadmeForge</strong> · Verify generated details before publishing</sub></p>",
        "",
        f"![Language](https://img.shields.io/badge/language-{re.sub(r'[^A-Za-z0-9]+', '-', str(profile['language'])).strip('-')}-2563eb)",
        f"![Files inspected](https://img.shields.io/badge/files%20inspected-{profile['file_count']}-334155)",
        "",
        "## What it is",
        "",
        summary,
        "",
        "## Quick start",
        "",
        "### Install",
        "",
        _code(profile["install_command"]),
        "",
        "### Run",
        "",
        _code(profile["run_command"]),
        "",
        "> These commands are inferred from repository metadata and file layout. Review them against your project's actual release and deployment workflow before publishing this README.",
        "",
        "## Repository map",
        "",
        "| Path | Why it matters |",
        "| --- | --- |",
    ]
    for path in profile.get("project_tree", [])[:28]:
        lower = path.lower()
        role = "Project metadata" if PathLike(path) in {"pyproject.toml", "package.json", "Cargo.toml", "go.mod"} else "Automated checks" if ".github/workflows/" in path else "Tests and regression coverage" if re.search(r"(^|/)(tests?|__tests__)(/|$)", path, re.I) else "Documentation" if lower.startswith(("docs/", "doc/")) else "Source or project file"
        lines.append(f"| `{_cell(path)}` | {role} |")
    if len(profile.get("project_tree", [])) == 0:
        lines.append("| *(No representative files detected)* | Add source, tests, and project metadata to make this section more informative. |")

    lines.extend(["", "## Detected project facts", "", "| Signal | Observed value |", "| --- | --- |", f"| Main language | {_cell(profile['language'])} |", f"| Package manager | {_cell(profile['package_manager'])} |", f"| License file | `{_cell(profile.get('license') or 'Not detected')}` |", f"| Automated test files | {len(profile.get('test_files', []))} |", f"| CI workflow files | {len(profile.get('workflow_files', []))} |", f"| Source files | {len(profile.get('source_files', []))} (sample capped at 120) |"])
    if profile.get("python_requires"):
        lines.append(f"| Python requirement | `{_cell(profile['python_requires'])}` |")
    if profile.get("entrypoints"):
        lines.extend(["", "### Detected entry points", "", "| Name | Type | Definition |", "| --- | --- | --- |"])
        for entry in profile["entrypoints"][:30]:
            lines.append(f"| `{_cell(entry['name'])}` | {_cell(entry['kind'])} | `{_cell(entry['target'])}` |")
    if profile.get("dependencies"):
        lines.extend(["", "### Declared runtime dependencies", "", *[f"- `{_cell(item)}`" for item in profile["dependencies"][:30]]])
        if len(profile["dependencies"]) > 30:
            lines.append(f"- … and {len(profile['dependencies']) - 30} more detected dependencies")
    else:
        lines.extend(["", "No runtime dependency declarations were detected from the supported manifest files."])
    lines.extend([
        "",
        "## Architecture at a glance",
        "",
        "```mermaid",
        "flowchart LR",
        "    A[Developer or CI] --> B[Project entry point]",
        "    B --> C[Core modules]",
        "    C --> D[Outputs / results]",
        "    E[Tests] -. verify .-> C",
        "    F[Project metadata] --> B",
        "```",
        "",
        "This is a generic orientation diagram, not a reverse-engineered runtime trace. Replace it with a project-specific architecture once the real module boundaries are confirmed.",
        "",
        "## Testing and automation",
        "",
    ])
    if profile.get("test_files"):
        lines.append(f"The scan detected **{len(profile['test_files'])} test-related files**. The recommended command inferred from the package layout is:")
        lines.extend(["", _code("python -m pytest" if profile["language"] == "Python" else "npm test" if profile["language"] in {"JavaScript", "TypeScript"} else "go test ./..." if profile["language"] == "Go" else "Review the repository's test runner configuration."), ""])
    else:
        lines.append("No recognizable test files were detected by this scan. Add automated tests and document how they are executed before describing the project as validated.")
    if profile.get("workflow_files"):
        lines.append("Detected CI workflow files:")
        lines.extend(["", *[f"- `{p}`" for p in profile["workflow_files"][:20]], ""])
    else:
        lines.append("No GitHub Actions workflow files were detected. Consider adding lint, unit tests, package-build checks, and a supported-runtime matrix.")
    lines.extend([
        "## Scope and verification notes",
        "",
        "ReadmeForge inspects files and package metadata locally. It does **not** install dependencies, import project code, execute scripts, query online services, or certify correctness. File counts and entry points are evidence from the current checkout, not guarantees that every documented path works.",
        "",
        "Before publishing, verify every generated command on a clean environment, replace generic architecture notes with system-specific facts, add real examples, and review all claims about security, performance, and compatibility.",
        "",
        "## Contributing",
        "",
        "1. Reproduce the issue with a small local fixture.",
        "2. Add a regression test that demonstrates the expected behavior.",
        "3. Run the test suite and formatting/lint checks before opening a pull request.",
        "4. Keep generated documentation explicit about what was observed and what remains an assumption.",
        "",
        "## License",
        "",
        f"The repository contains `{profile.get('license') or 'no detectable license file'}`. Confirm the license terms in the source repository before redistributing this project.",
        "",
        "---",
        "<sub>Generated by VerityAgent ReadmeForge. Treat this README as a reviewed draft, not a substitute for product documentation.</sub>",
        "",
    ])
    return "\n".join(lines)


def PathLike(path: str) -> str:
    return path.replace("\\", "/")


def render_json(profile: dict[str, Any]) -> str:
    return json.dumps(profile, indent=2, ensure_ascii=False) + "\n"
