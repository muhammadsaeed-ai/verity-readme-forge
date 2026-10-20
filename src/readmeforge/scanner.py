"""Local repository inspection. This module never contacts the network or executes project code."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

_IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", "coverage",
}
_MAX_FILES = 5_000
_MAX_TEXT_BYTES = 512_000


class InspectionError(ValueError):
    """Raised when a repository path cannot be inspected safely."""


def _read_text(path: Path, limit: int = _MAX_TEXT_BYTES) -> str | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _load_pyproject(path: Path) -> dict[str, Any]:
    raw = _read_text(path)
    if not raw:
        return {}
    try:
        value = tomllib.loads(raw)
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {"_parse_error": "pyproject.toml could not be parsed as TOML"}


def _readme_summary(text: str | None) -> str | None:
    if not text:
        return None
    lines = text.splitlines()
    seen_heading = False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            seen_heading = True
            continue
        if seen_heading and (line.startswith("![") or line.startswith("<") or line.startswith("[") or line.startswith("---")):
            continue
        if line.startswith(("![", "<", "---", "[![")):
            continue
        line = re.sub(r"[`*_~]", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            return line[:240]
    return None


def _guess_language(files: list[Path]) -> str:
    counts = Counter(p.suffix.lower() for p in files)
    if any(p.name == "pyproject.toml" or p.name in {"setup.py", "setup.cfg"} for p in files):
        return "Python"
    if any(p.name == "package.json" for p in files):
        return "JavaScript / TypeScript"
    if any(p.name == "Cargo.toml" for p in files):
        return "Rust"
    if any(p.name == "go.mod" for p in files):
        return "Go"
    ext_names = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".rs": "Rust", ".go": "Go", ".java": "Java", ".cs": "C#", ".rb": "Ruby", ".php": "PHP"}
    ranked = [(count, ext_names.get(ext)) for ext, count in counts.items() if ext in ext_names]
    ranked = [(count, name) for count, name in ranked if name]
    return max(ranked, default=(0, "Mixed / unknown"))[1]


def _tree(files: list[Path], root: Path, max_entries: int = 28) -> list[str]:
    items: list[str] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if relative in {"README.md", "LICENSE", "pyproject.toml", "package.json"} or relative.count("/") <= 2:
            items.append(relative)
    return sorted(dict.fromkeys(items))[:max_entries]


def inspect_repository(path: str | Path) -> dict[str, Any]:
    """Inspect project metadata and layout without importing or running project code."""
    root = Path(path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise InspectionError(f"Repository path is not a directory: {root}")

    files: list[Path] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(current)
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in _IGNORED_DIRS and not (base / name).is_symlink()
        )
        for name in sorted(filenames):
            candidate = base / name
            if candidate.is_symlink() or not candidate.is_file():
                continue
            files.append(candidate)
            if len(files) >= _MAX_FILES:
                break
        if len(files) >= _MAX_FILES:
            break
    files.sort(key=lambda item: item.relative_to(root).as_posix().casefold())
    relative_files = [p.relative_to(root).as_posix() for p in files]
    file_set = set(relative_files)

    pyproject = _load_pyproject(root / "pyproject.toml") if "pyproject.toml" in file_set else {}
    project = pyproject.get("project", {}) if isinstance(pyproject.get("project"), dict) else {}
    package_data: dict[str, Any] = {}
    package_name = None
    if "package.json" in file_set:
        try:
            parsed_package = json.loads((_read_text(root / "package.json") or "{}"))
            if isinstance(parsed_package, dict):
                package_data = parsed_package
            else:
                package_data = {"_parse_error": "package.json must contain a JSON object"}
        except json.JSONDecodeError:
            package_data = {"_parse_error": "package.json could not be parsed as JSON"}
        package_name = package_data.get("name")

    readme_text = _read_text(root / "README.md") or _read_text(root / "readme.md")
    name = str(project.get("name") or package_name or root.name).strip() or root.name
    summary = str(project.get("description") or package_data.get("description") or _readme_summary(readme_text) or f"A software project in `{root.name}`.").strip()
    language = _guess_language(files)

    entrypoints: list[dict[str, str]] = []
    scripts = project.get("scripts", {})
    if isinstance(scripts, dict):
        for script_name, target in sorted(scripts.items(), key=lambda pair: str(pair[0])):
            entrypoints.append({"name": str(script_name), "target": str(target), "kind": "Python console script"})
    node_scripts = package_data.get("scripts", {}) if isinstance(package_data, dict) else {}
    if isinstance(node_scripts, dict):
        for script_name, target in sorted(node_scripts.items(), key=lambda pair: str(pair[0])):
            entrypoints.append({"name": str(script_name), "target": str(target), "kind": "package.json script"})

    tests = [p for p in relative_files if re.search(r"(^|/)(tests?|__tests__)(/|$)", p, re.I) or re.search(r"(^|/)(test_[^/]+\.py|[^/]+\.(test|spec)\.[cm]?[jt]sx?)$", p, re.I)]
    workflows = [p for p in relative_files if p.startswith(".github/workflows/") and Path(p).suffix.lower() in {".yml", ".yaml"}]
    docs = [p for p in relative_files if p.startswith(("docs/", "doc/"))]
    source = [p for p in relative_files if p.startswith(("src/", "lib/", "app/")) and Path(p).suffix.lower() in {".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".go", ".java"}]
    license_path = next((p for p in relative_files if Path(p).name.lower() in {"license", "license.md", "license.txt", "copying"}), None)

    dependencies: list[str] = []
    raw_deps = project.get("dependencies", [])
    if isinstance(raw_deps, list):
        dependencies.extend(str(value) for value in raw_deps[:80])
    elif isinstance(raw_deps, dict):
        dependencies.extend(str(value) for value in raw_deps.keys())
    node_deps = package_data.get("dependencies", {}) if isinstance(package_data, dict) else {}
    if isinstance(node_deps, dict):
        dependencies.extend(f"{key}@{value}" for key, value in list(node_deps.items())[:80])
    if not dependencies and "requirements.txt" in file_set:
        requirements = _read_text(root / "requirements.txt") or ""
        dependencies = [line.strip() for line in requirements.splitlines() if line.strip() and not line.lstrip().startswith(("#", "-"))][:80]

    if language == "Python":
        install_command = "python -m pip install ." if "pyproject.toml" in file_set or "setup.py" in file_set else "python -m pip install -r requirements.txt" if "requirements.txt" in file_set else "No package installer detected; see the source files."
        preferred_entry = entrypoints[0]["name"] if entrypoints and entrypoints[0]["kind"] == "Python console script" else None
        run_command = f"{preferred_entry} --help" if preferred_entry else "python -m pytest" if tests else "python -m <module> --help (replace <module> with the project module)"
    elif language in {"JavaScript", "TypeScript"}:
        install_command = "npm install" if "package-lock.json" in file_set else "npm install (or the repository's declared package manager)"
        run_command = "npm test" if "test" in node_scripts else "npm run" if node_scripts else "npm start" if "start" in node_scripts else "Inspect package.json for the available scripts."
    elif language == "Rust":
        install_command, run_command = "cargo build", "cargo run -- --help"
    elif language == "Go":
        install_command, run_command = "go mod download", "go test ./..."
    else:
        install_command, run_command = "Follow the install instructions in the repository's source documentation.", "Review the project's documented entry point."

    metadata_notes: list[str] = []
    if pyproject.get("_parse_error"):
        metadata_notes.append(str(pyproject["_parse_error"]))
    if package_data.get("_parse_error"):
        metadata_notes.append(str(package_data["_parse_error"]))
    if len(files) >= _MAX_FILES:
        metadata_notes.append(f"File inventory was capped at {_MAX_FILES} files.")
    if not tests:
        metadata_notes.append("No test files or test directories were detected; this is not proof that tests do not exist elsewhere.")
    if not workflows:
        metadata_notes.append("No GitHub Actions workflow files were detected.")

    return {
        "schema_version": "readmeforge.profile/v1",
        "root": str(root),
        "name": name,
        "summary": summary,
        "language": language,
        "python_requires": project.get("requires-python"),
        "package_manager": "pip / Python packaging" if language == "Python" else "npm-compatible" if language in {"JavaScript", "TypeScript"} else language,
        "install_command": install_command,
        "run_command": run_command,
        "license": license_path,
        "entrypoints": entrypoints,
        "dependencies": dependencies,
        "file_count": len(files),
        "source_files": source[:120],
        "test_files": tests[:120],
        "workflow_files": workflows,
        "documentation_files": docs[:120],
        "project_tree": _tree(files, root),
        "metadata_notes": metadata_notes,
        "existing_readme": bool(readme_text),
        "repository_url": next((str(project.get("urls", {}).get(key)) for key in ("Repository", "Homepage") if isinstance(project.get("urls"), dict) and project.get("urls", {}).get(key)), None),
    }
