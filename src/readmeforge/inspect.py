"""Inspect repository evidence without executing the inspected project."""

from __future__ import annotations

import fnmatch
import json
import os
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from readmeforge import SCHEMA_VERSION, __version__
from readmeforge.errors import ReadmeForgeError

EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "vendor",
    "dist", "build", "target", ".tox", ".nox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "__pycache__", "site-packages", ".idea", ".vscode", ".next",
    ".nuxt", ".turbo", ".cache", "coverage", "htmlcov",
}
EXCLUDED_FILES = {".DS_Store", "Thumbs.db"}
MAX_FILES = 50_000
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024

LANGUAGE_EXTENSIONS = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".php": "PHP", ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C", ".h": "C/C++",
    ".swift": "Swift", ".dart": "Dart", ".scala": "Scala", ".lua": "Lua",
    ".sh": "Shell", ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".vue": "Vue", ".svelte": "Svelte", ".md": "Markdown", ".mdx": "MDX",
}
MANIFESTS = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "package.json",
    "pnpm-lock.yaml", "yarn.lock", "package-lock.json", "Cargo.toml", "go.mod",
    "composer.json", "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts",
    "CMakeLists.txt", "Makefile", "Pipfile", "poetry.lock", "uv.lock", "deno.json",
    "deno.jsonc",
}


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_ignore(path: Path, base: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rules: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("\\#") or line.startswith("\\!"):
            line = line[1:]
        negate = line.startswith("!")
        if negate:
            line = line[1:]
        if not line:
            continue
        directory_only = line.endswith("/")
        anchored = line.startswith("/")
        pattern = line.strip("/")
        if pattern:
            rules.append({
                "base": base, "pattern": pattern, "negate": negate,
                "directory_only": directory_only, "anchored": anchored,
                "has_slash": "/" in pattern,
            })
    return rules


def _matches_rule(rule: dict[str, Any], relative: str, is_dir: bool) -> bool:
    base = str(rule["base"])
    if base and relative.startswith(base + "/"):
        candidate = relative[len(base) + 1:]
    elif base and relative == base:
        candidate = ""
    elif base:
        return False
    else:
        candidate = relative
    if not candidate:
        return False
    parts = candidate.split("/")
    if rule["directory_only"] and not is_dir:
        candidates = ["/".join(parts[:index]) for index in range(1, len(parts))]
    else:
        candidates = [candidate] + ["/".join(parts[:index]) for index in range(1, len(parts))]
    pattern = str(rule["pattern"])
    if rule["has_slash"] or rule["anchored"]:
        return any(fnmatch.fnmatchcase(value, pattern) for value in candidates)
    return any(fnmatch.fnmatchcase(part, pattern) for value in candidates for part in value.split("/"))


def _is_ignored(relative: str, is_dir: bool, rules: list[dict[str, Any]], extra: tuple[str, ...]) -> bool:
    parts = Path(relative).parts
    directory_parts = parts if is_dir else parts[:-1]
    if any(part in EXCLUDED_DIRS for part in directory_parts):
        return True
    if not is_dir and parts and parts[-1] in EXCLUDED_FILES:
        return True
    ignored = False
    for pattern in extra:
        if fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(Path(relative).name, pattern):
            ignored = True
    for rule in rules:
        if _matches_rule(rule, relative, is_dir):
            ignored = not bool(rule["negate"])
    return ignored


def _read_limited(path: Path, limit: int = MAX_MANIFEST_BYTES) -> str | None:
    try:
        with path.open("rb") as handle:
            payload = handle.read(limit + 1)
        if len(payload) > limit:
            return None
        return payload.decode("utf-8-sig", errors="replace")
    except OSError:
        return None


def _toml_summary(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    try:
        import tomllib
        value = tomllib.loads(text)
        parsed = value if isinstance(value, dict) else {}
    except ImportError:
        parsed = {}
    except (TypeError, ValueError):
        parsed = {}
    project = parsed.get("project", {})
    if isinstance(project, dict) and project:
        scripts = project.get("scripts", {})
        deps = project.get("dependencies", [])
        return {
            "name": project.get("name") if isinstance(project.get("name"), str) else None,
            "description": project.get("description") if isinstance(project.get("description"), str) else None,
            "requires_python": project.get("requires-python") if isinstance(project.get("requires-python"), str) else None,
            "scripts": {str(key): str(value) for key, value in scripts.items()} if isinstance(scripts, dict) else {},
            "dependency_count": len(deps) if isinstance(deps, list) else 0,
        }

    def find(pattern: str) -> str | None:
        found = re.search(pattern, text, re.MULTILINE)
        return found.group(1).strip() if found else None

    scripts: dict[str, str] = {}
    script_section = re.search(r"(?ms)^\[project\.scripts\]\s*(.*?)(?=^\[|\Z)", text)
    if script_section:
        for line in script_section.group(1).splitlines():
            match = re.match(r"""^\s*([A-Za-z0-9_.-]+)\s*=\s*(['"])(.*?)\2\s*$""", line)
            if match:
                scripts[match.group(1)] = match.group(2)
    return {
        "name": find(r"^\s*name\s*=\s*['\\"]([^'\\"]+)['\\"]"),
        "description": find(r"^\s*description\s*=\s*['\\"]([^'\\"]+)['\\"]"),
        "requires_python": find(r"^\s*requires-python\s*=\s*['\\"]([^'\\"]+)['\\"]"),
        "scripts": scripts,
        "dependency_count": 0,
    }


def _category(relative: str) -> str:
    path = Path(relative)
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if "tests" in parts or "test" in parts or "__tests__" in parts or name.startswith("test_") or name.endswith("_test.py") or ".test." in name:
        return "test"
    if "docs" in parts or "documentation" in parts or path.suffix.lower() in {".md", ".rst", ".adoc"}:
        return "documentation"
    if name in MANIFESTS or name.startswith("requirements") or name in {".gitignore", ".editorconfig", "license", "dockerfile"}:
        return "configuration"
    if path.suffix.lower() in LANGUAGE_EXTENSIONS:
        return "source"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}:
        return "asset"
    return "other"


def inspect_repository(
    repository: str | os.PathLike[str] = ".",
    *,
    excludes: Iterable[str] = (),
    max_files: int = MAX_FILES,
) -> dict[str, Any]:
    """Inspect local paths and selected manifests; target project code is never executed."""
    raw_root = Path(repository).expanduser()
    try:
        root = raw_root.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ReadmeForgeError(f"Repository path cannot be resolved: {raw_root!r}") from exc
    if not root.is_dir():
        raise ReadmeForgeError(f"Repository path is not a directory: {raw_root!r}")
    if max_files < 1:
        raise ReadmeForgeError("--max-files must be a positive integer.")

    extra = tuple(excludes)
    ignore_path = root / ".gitignore"
    rules_by_dir: dict[str, list[dict[str, Any]]] = {
        "": _read_ignore(ignore_path, "") if ignore_path.is_file() else []
    }
    files: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    def walk_error(error: OSError) -> None:
        warnings.append({
            "code": "DIRECTORY_READ_FAILED",
            "path": Path(error.filename or ".").name,
            "message": str(error)[:200],
        })

    for current_text, directories, names in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
        current = Path(current_text)
        current_rel = "" if current == root else _relative(current, root)
        inherited = list(rules_by_dir.get(current_rel, []))
        current_ignore = current / ".gitignore"
        if current_rel and current_ignore.is_file() and not current_ignore.is_symlink():
            inherited.extend(_read_ignore(current_ignore, current_rel))
        kept: list[str] = []
        for dirname in sorted(directories):
            candidate = current / dirname
            relative = _relative(candidate, root)
            if candidate.is_symlink() or _is_ignored(relative, True, inherited, extra):
                continue
            rules_by_dir[relative] = list(inherited)
            kept.append(dirname)
        directories[:] = kept
        for filename in sorted(names):
            candidate = current / filename
            relative = _relative(candidate, root)
            if candidate.is_symlink() or _is_ignored(relative, False, inherited, extra):
                continue
            try:
                size = candidate.stat().st_size
            except OSError as exc:
                warnings.append({"code": "FILE_STAT_FAILED", "path": relative, "message": str(exc)[:200]})
                continue
            if size > MAX_FILE_BYTES:
                warnings.append({"code": "FILE_TOO_LARGE", "path": relative, "message": f"Skipped file larger than {MAX_FILE_BYTES} bytes."})
                continue
            if len(files) >= max_files:
                raise ReadmeForgeError(
                    f"Repository exceeds --max-files={max_files}. Narrow the scan with --exclude or raise the limit."
                )
            files.append({
                "path": relative, "name": filename, "category": _category(relative),
                "extension": candidate.suffix.lower(), "language": LANGUAGE_EXTENSIONS.get(candidate.suffix, ""),
                "size_bytes": size,
            })

    files.sort(key=lambda item: item["path"].casefold())
    counters: Counter[str] = Counter(item["language"] for item in files if item["language"])
    manifest_paths = [item["path"] for item in files if item["name"] in MANIFESTS or item["name"].startswith("requirements")]
    root_names = {Path(path).name for path in manifest_paths if "/" not in path}
    manifest_warnings: list[dict[str, str]] = []
    pyproject: dict[str, Any] = {}
    if "pyproject.toml" in root_names:
        text = _read_limited(root / "pyproject.toml")
        if text is None:
            manifest_warnings.append({"code": "MANIFEST_NOT_PARSED", "path": "pyproject.toml", "message": "Manifest exceeds the read limit."})
        else:
            pyproject = _toml_summary(text)

    package: dict[str, Any] = {}
    if "package.json" in root_names:
        text = _read_limited(root / "package.json")
        if text is not None:
            try:
                value = json.loads(text)
                package = value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                manifest_warnings.append({"code": "MANIFEST_NOT_PARSED", "path": "package.json", "message": "Manifest is invalid JSON."})
        else:
            manifest_warnings.append({"code": "MANIFEST_NOT_PARSED", "path": "package.json", "message": "Manifest exceeds the read limit."})

    composer: dict[str, Any] = {}
    if "composer.json" in root_names:
        text = _read_limited(root / "composer.json")
        if text:
            try:
                value = json.loads(text)
                composer = value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                manifest_warnings.append({"code": "MANIFEST_NOT_PARSED", "path": "composer.json", "message": "Manifest is invalid JSON."})

    npm_raw = package.get("scripts", {})
    npm_scripts = {str(k): str(v) for k, v in npm_raw.items() if isinstance(v, str)} if isinstance(npm_raw, dict) else {}
    dependencies = package.get("dependencies", {})
    dev_dependencies = package.get("devDependencies", {})
    project_name = pyproject.get("name") or package.get("name") or composer.get("name") or root.name.replace("_", "-")
    description = pyproject.get("description") or package.get("description") or composer.get("description")
    if not isinstance(description, str) or not description.strip():
        description = f"Documentation for {project_name}, generated from local repository evidence."
    description = " ".join(description.split())[:400]

    top_dirs = sorted({item["path"].split("/", 1)[0] for item in files if "/" in item["path"]}, key=str.casefold)
    top_files = sorted({item["path"] for item in files if "/" not in item["path"]}, key=str.casefold)
    test_paths = sorted(item["path"] for item in files if item["category"] == "test")
    docs = sorted(
        item["path"] for item in files
        if item["category"] == "documentation" and Path(item["path"]).name.lower() not in {"readme.md", "readme.rst"}
    )
    ci = sorted(
        item["path"] for item in files
        if item["path"].startswith(".github/workflows/") or item["path"].startswith(".gitlab/ci")
        or Path(item["path"]).name in {"Jenkinsfile", ".travis.yml", "azure-pipelines.yml"}
    )
    readmes = sorted(item["path"] for item in files if Path(item["path"]).name.lower().startswith("readme"))
    licenses = sorted(
        item["path"] for item in files
        if Path(item["path"]).name.lower() in {"license", "license.md", "license.txt", "copying"}
    )
    contributions = sorted(
        item["path"] for item in files
        if Path(item["path"]).name.lower().startswith(("contributing", "code_of_conduct"))
    )
    sources = [item["path"] for item in files if item["category"] == "source"]

    evidence = []
    if manifest_paths:
        evidence.append(f"Detected manifest(s): {', '.join(manifest_paths[:8])}")
    if sources:
        evidence.append(f"Found {len(sources)} files with recognized source-code extensions.")
    if test_paths:
        evidence.append(f"Found {len(test_paths)} test-classified path(s).")
    if docs:
        evidence.append(f"Found {len(docs)} additional documentation file(s).")
    if ci:
        evidence.append(f"Found {len(ci)} CI configuration file(s).")
    if licenses:
        evidence.append(f"Found a license file: {licenses[0]}.")
    if readmes:
        evidence.append(f"Found an existing README: {readmes[0]}.")

    install_commands: list[dict[str, str]] = []
    if "pyproject.toml" in root_names:
        install_commands.append({"label": "Python package", "command": "python -m pip install .", "note": "Inferred from pyproject.toml; review its build configuration before running."})
    elif "requirements.txt" in root_names:
        install_commands.append({"label": "Python requirements", "command": "python -m pip install -r requirements.txt", "note": "Inferred from requirements.txt."})
    if "package.json" in root_names:
        manager = "pnpm" if "pnpm-lock.yaml" in root_names else ("yarn" if "yarn.lock" in root_names else "npm")
        install_commands.append({"label": "JavaScript / TypeScript", "command": f"{manager} install", "note": f"Manager inferred from root lockfiles: {manager}."})
    if "Cargo.toml" in root_names:
        install_commands.append({"label": "Rust", "command": "cargo build", "note": "Inferred from Cargo.toml."})
    if "go.mod" in root_names:
        install_commands.append({"label": "Go", "command": "go build ./...", "note": "Inferred from go.mod."})
    if "composer.json" in root_names:
        install_commands.append({"label": "PHP / Composer", "command": "composer install", "note": "Inferred from composer.json."})
    if "Gemfile" in root_names:
        install_commands.append({"label": "Ruby / Bundler", "command": "bundle install", "note": "Inferred from Gemfile."})

    manager = "pnpm" if "pnpm-lock.yaml" in root_names else ("yarn" if "yarn.lock" in root_names else "npm")
    test_commands: list[dict[str, str]] = []
    if "test" in npm_scripts:
        test_commands.append({"label": "JavaScript test script", "command": f"{manager} test"})
    if "pytest.ini" in top_files or "tox.ini" in top_files or any(path.startswith("tests/") for path in test_paths):
        test_commands.append({"label": "Python test candidate", "command": "python -m pytest", "note": "Candidate inferred from test/config paths; verify the test-runner dependency."})
    if "go.mod" in root_names and counters.get("Go", 0):
        test_commands.append({"label": "Go tests", "command": "go test ./..."})
    if "Cargo.toml" in root_names and counters.get("Rust", 0):
        test_commands.append({"label": "Rust tests", "command": "cargo test"})

    run_commands: list[dict[str, str]] = []
    for script_name in ("dev", "start", "serve", "preview", "build", "lint", "typecheck"):
        if script_name in npm_scripts:
            run_commands.append({"label": f"package script: {script_name}", "command": f"{manager} run {script_name}", "definition": npm_scripts[script_name]})
    py_scripts = pyproject.get("scripts", {})
    if isinstance(py_scripts, dict):
        for script_name, target in sorted(py_scripts.items()):
            run_commands.append({"label": f"Python console script: {script_name}", "command": str(script_name), "definition": str(target)})

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "readmeforge", "version": __version__},
        "project": {
            "name": str(project_name),
            "description": description,
            "primary_language": counters.most_common(1)[0][0] if counters else "Unknown",
            "languages": [{"name": language, "file_count": count} for language, count in sorted(counters.items(), key=lambda pair: (-pair[1], pair[0].casefold()))[:12]],
            "python_requirement": pyproject.get("requires_python"),
            "package_scripts": {"python": py_scripts if isinstance(py_scripts, dict) else {}, "node": npm_scripts},
            "dependency_counts": {
                "python": pyproject.get("dependency_count", 0),
                "node": len(dependencies) if isinstance(dependencies, dict) else 0,
                "node_dev": len(dev_dependencies) if isinstance(dev_dependencies, dict) else 0,
            },
        },
        "summary": {
            "file_count": len(files), "source_file_count": len(sources), "test_path_count": len(test_paths),
            "documentation_file_count": len(docs), "manifest_count": len(manifest_paths),
            "has_readme": bool(readmes), "has_license": bool(licenses),
            "has_tests": bool(test_paths) or bool(test_commands), "has_ci": bool(ci),
        },
        "manifests": sorted(manifest_paths, key=str.casefold),
        "top_level_directories": top_dirs[:40],
        "top_level_files": top_files[:60],
        "test_paths": test_paths[:40],
        "documentation_paths": docs[:40],
        "ci_paths": ci[:20],
        "readme_paths": readmes[:8],
        "license_paths": licenses[:8],
        "contribution_paths": contributions[:8],
        "install_commands": install_commands,
        "test_commands": test_commands,
        "run_commands": run_commands,
        "evidence": evidence,
        "warnings": warnings + manifest_warnings,
        "analysis": {
            "project_code_executed": False, "network_requests_made": False,
            "absolute_path_recorded": False, "max_files": max_files,
            "limitations": [
                "The inspector reads names and selected manifests; it does not infer runtime behavior.",
                "Detected commands are recommendations, not proof that they work.",
                "A file tree cannot prove a product feature exists or is production-ready.",
                "Ignore-file handling implements a useful subset of Git ignore semantics.",
            ],
        },
        "files": files,
    }
