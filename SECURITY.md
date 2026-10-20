# Security policy

## Design intent

ReadmeForge treats the inspected repository as data. It inventories local paths and reads selected bounded manifests. It does not import or execute target code, install the target's dependencies, or make network requests.

## Potentially sensitive output

Generated documents can disclose repository names, file paths, project scripts, dependencies, or license details. Review output before sharing it publicly. Detected scripts are suggestions and are never executed by ReadmeForge.

## Reporting a concern

Report suspected path traversal, unbounded resource use, unintended file reads, Markdown injection, or code execution through GitHub's private vulnerability-reporting feature when available. Avoid posting sensitive data or exploit details in public issues.

The project is alpha software and has not been independently audited or security-certified.
