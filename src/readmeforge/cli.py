"""Command-line interface for ReadmeForge."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from readmeforge import __version__
from readmeforge.errors import ReadmeForgeError
from readmeforge.inspect import inspect_repository
from readmeforge.render import render_json_report, render_readme


def _write_output(filename: str, content: str, *, force: bool = False) -> Path:
    target = Path(filename).expanduser().absolute()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ReadmeForgeError(f"Cannot create output directory {target.parent}: {exc}") from exc
    if target.exists() and not force:
        raise ReadmeForgeError(f"Output already exists: {target}. Use --force to replace it intentionally.")
    descriptor = None
    temporary = None
    try:
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.readmeforge-", suffix=".tmp", dir=target.parent)
        temporary = Path(temp_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if force:
            os.replace(temporary, target)
        else:
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise ReadmeForgeError(f"Output already exists: {target}. Use --force to replace it intentionally.") from exc
            temporary.unlink()
        return target
    except ReadmeForgeError:
        raise
    except (OSError, ValueError) as exc:
        raise ReadmeForgeError(f"Could not write output to {target}: {exc}") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="readmeforge",
        description="Generate README drafts from local repository evidence.",
        epilog="The inspector reads file metadata and selected manifests; it never executes the inspected project.",
    )
    parser.add_argument("--version", action="version", version=f"ReadmeForge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Inspect repository structure and manifest evidence.")
    inspect.add_argument("repository", nargs="?", default=".")
    inspect.add_argument("--format", choices=("text", "json"), default="text")
    inspect.add_argument("-o", "--output", help="Output file, or '-' for stdout.")
    inspect.add_argument("--exclude", action="append", default=[], help="Extra exclusion glob; repeatable.")
    inspect.add_argument("--max-files", type=int, default=50_000)
    generate = sub.add_parser("generate", help="Generate a Markdown README draft.")
    generate.add_argument("repository", nargs="?", default=".")
    generate.add_argument("-o", "--output", default="README.generated.md")
    generate.add_argument("--title", help="Optional title override.")
    generate.add_argument("--force", action="store_true", help="Replace an existing output file.")
    generate.add_argument("--exclude", action="append", default=[], help="Extra exclusion glob; repeatable.")
    generate.add_argument("--max-files", type=int, default=50_000)
    check = sub.add_parser("check", help="Check whether README.md matches generated content.")
    check.add_argument("repository", nargs="?", default=".")
    check.add_argument("-f", "--file", default="README.md")
    check.add_argument("--title", help="Optional title override.")
    check.add_argument("--exclude", action="append", default=[], help="Extra exclusion glob; repeatable.")
    check.add_argument("--max-files", type=int, default=50_000)
    return parser


def _inspect_text(report: dict[str, Any]) -> str:
    project = report["project"]
    summary = report["summary"]
    lines = [
        f"ReadmeForge inspection: {project['name']}",
        f"Primary language: {project['primary_language']}",
        f"Files inventoried: {summary['file_count']}",
        f"Source files: {summary['source_file_count']}",
        f"Test paths: {summary['test_path_count']}",
        f"Project manifests: {summary['manifest_count']}",
        f"CI configuration: {'detected' if summary['has_ci'] else 'not detected'}",
        f"License file: {'detected' if summary['has_license'] else 'not detected'}",
        "", "Detected signals:",
    ]
    lines.extend(f"  - {item}" for item in report["evidence"][:12])
    if report["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"  - {item['code']}: {item['message']}" for item in report["warnings"][:12])
    lines.extend(["", "Static inspection only: project code was not executed; no network calls were made."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        scan_excludes = list(getattr(args, "exclude", []))
        # Keep generated output out of the inventory so a README generated
        # in-place remains deterministic when checked on the next run.
        try:
            scan_root = Path(args.repository).expanduser().resolve(strict=True)
            candidate = None
            if args.command == "generate" and args.output != "-":
                candidate = Path(args.output).expanduser().resolve(strict=False)
            elif args.command == "check":
                candidate = Path(args.file).expanduser()
                if not candidate.is_absolute():
                    candidate = scan_root / candidate
                candidate = candidate.resolve(strict=False)
            if candidate is not None:
                relative_output = candidate.relative_to(scan_root).as_posix()
                if relative_output not in {"", "."} and relative_output not in scan_excludes:
                    scan_excludes.append(relative_output)
        except (OSError, RuntimeError, ValueError):
            pass
        report = inspect_repository(
            args.repository,
            excludes=scan_excludes,
            max_files=getattr(args, "max_files", 50_000),
        )
        if args.command == "inspect":
            output = render_json_report(report) if args.format == "json" else _inspect_text(report)
            if not args.output or args.output == "-":
                sys.stdout.write(output)
            else:
                target = _write_output(args.output, output)
                print(f"Inspection report written to {target}")
            return 0
        if args.command == "generate":
            output = render_readme(report, title=args.title)
            if args.output == "-":
                sys.stdout.write(output)
            else:
                target = _write_output(args.output, output, force=args.force)
                print(f"README generated: {target}")
                print("Review inferred commands, project claims, and license details before publishing.")
            return 0
        if args.command == "check":
            target = Path(args.file).expanduser()
            if not target.is_absolute():
                target = Path(args.repository).expanduser() / target
            generated = render_readme(report, title=args.title)
            try:
                existing = target.read_text(encoding="utf-8")
            except FileNotFoundError:
                print(f"README is missing: {target}")
                return 1
            except (OSError, UnicodeError) as exc:
                raise ReadmeForgeError(f"Cannot read README {target}: {exc}") from exc
            if existing == generated:
                print(f"README is up to date: {target}")
                return 0
            print(f"README is out of date: {target}")
            print(f"Preview the generated version with: readmeforge generate {args.repository} --output README.generated.md")
            return 1
        parser.error(f"Unknown command: {args.command}")
        return 2
    except ReadmeForgeError as exc:
        print(f"readmeforge: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("readmeforge: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
