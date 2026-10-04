# Engineering notes: llm-cost-guard

## Purpose and scope

Token estimation and persisted LLM budget controls. This repository is an independently inspectable project; customer adoption, production scale and commercial readiness are not claimed without evidence.

## Request and data flow

Estimate/usage request → pricing and token calculations → transactional budget checks → stored usage, alerts and dashboard.

## Implementation map

Primary implementation and review locations: `app`, `tests`, `migrations`. Dependency manifests and `.github/workflows/` specify installation and automated checks. Read the source for exact contracts and data models.

## Local verification

From `.` in a configured virtual environment:

```sh
pip install -r requirements-dev.txt
ruff check .
mypy app
pytest -q
```

From the repository root, run `python scripts/repository_check.py` for documentation and tracked-file checks. CI evidence is available in [GitHub Actions](https://github.com/Jemade/llm-cost-guard/actions). Green hygiene checks alone do not mean application tests passed.

## Decisions and boundaries

Estimates depend on configured prices and tokenizer behavior. Pricing must be maintained. Passing local tests is not evidence of tested production throughput.

Use the README's current run instructions and configuration examples. Keep provider credentials outside Git. Test changes against controlled fixtures before enabling external services. Health checks indicate process/service state, not end-to-end correctness.

## Review and operational evidence

[Review checklist](REVIEW_CHECKLIST.md) distinguishes repository evidence from outstanding human and deployment validation. Report measured workload, environment and method with any performance claim. Document incident fixes through reproducible issues and regression tests; do not invent user counts or peer reviews.

## Reuse and licensing

No repository-wide reuse license has been selected. Public visibility alone does not grant an open-source reuse license. Ownership and third-party asset rights must be confirmed before licensing this project.
