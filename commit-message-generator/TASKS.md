# Tasks

## Fix `UnicodeDecodeError` / `NoneType` crash when reading git output on Windows

**Symptom** (seen when running the installed prepare-commit-msg hook):

```
Exception in thread Thread-3 (_readerthread):
...
  File ".../encodings/cp1252.py", line 23, in decode
    return codecs.charmap_decode(input,self.errors,decoding_table)[0]
UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 2819: character maps to <undefined>
Traceback (most recent call last):
  File ".../generate_commit_message.py", line 197, in <module>
    sys.exit(main())
  ...
  File ".../generate_commit_message.py", line 69, in build_user_prompt
    if not diff.strip():
AttributeError: 'NoneType' object has no attribute 'strip'
```

**Root cause:** `subprocess.run(..., text=True)` decodes git's output using the
locale default codec (cp1252 on Windows). Git emits UTF-8, so a byte such as
`0x90` raises `UnicodeDecodeError` inside the subprocess reader thread. That
crash happens in a background thread, so `result.stdout` comes back as `None`,
which then surfaces as `AttributeError: 'NoneType' object has no attribute
'strip'` at `diff.strip()`.

**Fix:** force UTF-8 decoding (with a safe fallback) on the subprocess calls in
`generate_commit_message.py`.

- `run_git()` (the `subprocess.run` for git) — add:
  ```python
  encoding="utf-8",
  errors="replace",
  ```
- `call_claude()` (the `subprocess.run` for `claude -p`) — same treatment, so
  the `claude` process's stdout/stderr can't hit the same cp1252 decode crash.

Both currently pass only `text=True`, which is what triggers the locale-default
codec.
