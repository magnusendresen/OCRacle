# AGENT Instructions

This repository does not currently include automated tests.

- Do not attempt to install the libraries listes in requirements.txt
- Begin each session by checking for `AGENTS.md` files in the repository root and
  within any subdirectory related to files you modify.
- For Python changes, run a basic syntax check using:
  `python -m py_compile $(git ls-files '*.py')`
- For C++ code, if you modify files under `app`, compile using Meson:
  `meson setup builddir` (once) and `meson compile -C builddir`.
- Commit messages should be a single English sentence in the imperative mood.
- Summaries in pull requests must cite relevant lines using the `F:<path>`
  notation as described in system instructions.
- If commands fail because dependencies are missing or due to environment
  restrictions, note this explicitly in the testing section of your PR.
