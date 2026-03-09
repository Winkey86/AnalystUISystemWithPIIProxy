# Repository Guidelines

## Project Structure & Module Organization
This repository currently stores project documentation and build artifacts.
- `Docs/01_orchestrator_architecture_plan.md`: architecture and design decisions.
- `Docs/02_orchestrator_build_steps_codex_prompts_v2.md`: staged implementation roadmap and prompts.
- `Docs/latex/`: LaTeX source and generated auxiliary files for the explanatory note.
- `Docs/ПЗ_команда4.pdf`: compiled deliverable PDF.

Keep narrative content in `Docs/*.md`. Keep the canonical LaTeX source in `Docs/latex/*.tex` and avoid committing unnecessary temporary files if they can be regenerated.

## Build, Test, and Development Commands
Use LaTeX tooling from the repository root:
- `latexmk -pdf Docs/latex/poyasnitelnaya_zapiska_agentnyy_analitik_dannyh.tex` — build PDF with dependency tracking.
- `latexmk -c Docs/latex/poyasnitelnaya_zapiska_agentnyy_analitik_dannyh.tex` — clean auxiliary files (`.aux`, `.log`, `.toc`, etc.).
- `pdflatex Docs/latex/poyasnitelnaya_zapiska_agentnyy_analitik_dannyh.tex` — single-pass compile (useful for quick checks).

For Markdown edits, preview in your editor and verify heading hierarchy before commit.

## Coding Style & Naming Conventions
- Markdown: use concise sections, sentence-case prose, and explicit technical terms.
- LaTeX: keep commands on separate lines where practical; use consistent indentation (2 or 4 spaces, but do not mix styles within a block).
- File naming: prefer descriptive snake_case for technical assets (example: `orchestrator_architecture_plan.md`).
- Preserve existing Russian-language domain terminology and transliteration patterns already used in filenames.

## Testing Guidelines
There is no automated unit-test suite in this repository yet. Validation is document-focused:
- Build LaTeX without errors.
- Check `.log` for critical warnings (broken references, missing files).
- Manually review generated PDF formatting, table overflow, and links.

## Commit & Pull Request Guidelines
Git history is not available in this workspace snapshot, so follow a conventional format:
- Commit messages: imperative and scoped, e.g. `docs(latex): fix table width in section 4`.
- PRs should include: purpose, changed files, build/validation steps run, and before/after screenshots for layout-sensitive PDF changes.
- Keep PRs focused; separate structural refactors from content edits.
