# Changelog

Notable changes to the commit-message-generator. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## Unreleased

### Fixed

- **Encoding crash on Windows when the staged diff or generated message
  contained certain non-ASCII characters.** `generate_commit_message.py`
  decoded git/claude subprocess output with `text=True`, which uses the
  platform default codec (cp1252 on Windows) instead of UTF-8. A byte such as
  `0x90` (e.g. from `←`) or `0x8f` (e.g. `⏰`, `量`) is undefined in cp1252 and
  raised `UnicodeDecodeError` in the subprocess reader thread, leaving
  `stdout == None` and surfacing as `AttributeError: 'NoneType' ... 'strip'`.
  Now forces `encoding="utf-8", errors="replace"` at every subprocess boundary
  (`run_git`, `call_claude` in and out) and reconfigures the script's own
  stdout/stderr to UTF-8 so its `print` paths can't hit the same failure.
  See `TASKS.md` for the full analysis.
