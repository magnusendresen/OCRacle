# Guidelines for Codex Agents

This repository combines Python scripts and a C++ GUI for processing exam tasks.

## Repository overview
- `scripts/` contains Python logic for OCR, text processing and task separation.
- `app/` contains the C++ application built with Meson.
- `prompts/` stores prompt templates used in the pipeline.

## Development
- Keep commits focused and descriptive.
- When modifying any Python file run:
  ```bash
  python3 -m py_compile $(git ls-files '*.py')
  ```
  to ensure there are no syntax errors.
- There are currently no automated tests, but if test files are added run `pytest` before committing.

## Pull request instructions
Describe the changes and mention that the Python syntax check was run.
