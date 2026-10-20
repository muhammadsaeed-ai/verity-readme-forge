# ReadmeForge usage

## Install from source

~~~bash
git clone https://github.com/muhammadsaeed-ai/verity-readme-forge.git
cd verity-readme-forge
python -m venv .venv
~~~

Activate the environment, then run:

~~~bash
python -m pip install -e ".[dev]"
readmeforge --help
~~~

## Inspect first

~~~bash
readmeforge inspect .
readmeforge inspect . --format json --output readmeforge-report.json
~~~

The report includes recognized languages, manifest files, likely install/test commands, top-level directories, and configuration evidence. It does not embed source code.

## Generate a draft without replacing a human README

~~~bash
readmeforge generate . --output README.generated.md
~~~

Review the draft. Existing output files are never overwritten by default.

## Update README.md intentionally

~~~bash
readmeforge generate . --output README.md --force
~~~

The force option is explicit consent to replace the target file. ReadmeForge does not merge generated content with hand-authored prose.

## Check generated documentation in CI

~~~bash
readmeforge check .
~~~

Exit code 0 means the current README exactly matches generated content; exit code 1 indicates a missing or out-of-date README; exit code 2 indicates a usage or inspection error. A custom title supplied to check must match the title supplied to generate.

## Exclusions and limits

~~~bash
readmeforge inspect . --exclude "generated/**" --exclude "*.snap" --max-files 15000
readmeforge generate . --output README.generated.md --exclude "generated/**"
~~~

Custom exclusions supplement default exclusions and .gitignore rules. Ignore handling is pragmatic rather than a complete reimplementation of Git.

## Safety and review

ReadmeForge reads file metadata plus selected manifests. It never imports or executes the target project and makes no network requests. Verify generated commands, license details, package names, and product behavior before publishing. Do not run inferred commands from untrusted repositories blindly.
