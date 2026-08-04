# Changelog

Notable changes to the commit-message-generator. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## Unreleased

### Fixed

- **Hook crashed with a raw "command not found" when neither `python3` nor
  `python` was on PATH.** The `prepare-commit-msg` hook template in
  `install_hook.py` checked for `python3` and, if missing, blindly assumed
  `python` existed instead of checking for it too. On systems that ship only
  `python3` (e.g. Arch Linux) with a restricted PATH in the hook's shell
  environment, this printed a confusing shell-level "command not found"
  instead of the intentional, informative failure the rest of the tool uses
  (see `generate_commit_message.py`'s `error: ...` messages). Now checks for
  `python` explicitly too, and if neither is found, prints one clear
  diagnostic line and exits 0 without blocking the commit.

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
