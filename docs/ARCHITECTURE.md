# ReadmeForge architecture

ReadmeForge uses a small, inspectable pipeline. It discovers local file metadata and selected project manifests, builds a structured evidence report, and renders Markdown from that report. No source code from the analyzed project is imported or executed.

~~~mermaid
flowchart LR
    A[Local repository path] --> B[Ignore-aware file inventory]
    B --> C[Selected manifest readers]
    C --> D[Normalized evidence report]
    D --> E[README renderer]
    D --> F[JSON report]
    E --> G[Preview or atomic file write]
~~~

## Components

- inspect.py: filesystem traversal, common exclusions, practical ignore rules, manifest parsing, and evidence collection.
- render.py: normalized evidence to Markdown, JSON report output, and architecture file-layout diagrams.
- cli.py: argument validation, inspection, document generation, stale-documentation checks, and safe output handling.
- tests: isolated fixture repositories independent from this repository's own checkout.

## Safety model

1. Scans are local and bounded by file-count, per-file, and manifest-size limits.
2. Symlinked directories and files are skipped.
3. Common caches, virtual environments, build outputs, and vendor folders are excluded by default.
4. Reports contain relative paths, manifest metadata, and counts; source contents are not embedded.
5. Existing output is not replaced unless --force is supplied.
6. Detected commands are labeled as suggestions rather than verified run results.

## Current limitations

- Ignore patterns implement a useful subset of Git behavior, not every corner case.
- Repository features cannot be proven from file names alone; ReadmeForge avoids inventing product feature claims.
- Custom framework conventions, monorepo workspaces, private package registries, and generated code may need manual editing.
- Architecture diagrams describe detected file layout, not runtime call graphs.
- Commands inferred from package manifests should be inspected before execution.
