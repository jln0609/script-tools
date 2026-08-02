# Tasks

## Fix encoding crashes when the diff/message contains non-cp1252 characters (Windows)

**Symptom** (seen when running the installed prepare-commit-msg hook in
`MiseRecipeExtractor`, committing a new README + a one-line todo edit):

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

### Root cause

`subprocess.run(..., text=True)` decodes captured output using the **platform
default codec**, which on Windows is the legacy ANSI codepage `cp1252`. Git
emits UTF-8. When the diff contained a byte that cp1252 leaves undefined, the
decode raised `UnicodeDecodeError` *inside the subprocess reader thread* (hence
`Thread-3`). Because that crash is in a background thread, `subprocess.run`
returned with `result.stdout == None`, which then surfaced downstream as
`AttributeError: 'NoneType' object has no attribute 'strip'` at `diff.strip()`.
So the two tracebacks are one bug, not two.

### Why it triggered now (and why it's usually silent)

cp1252 defines a character for almost every byte in 0x80-0xFF. Only **five**
bytes are undefined and raise on decode:

```
0x81  0x8D  0x8F  0x90  0x9D
```

Everything else *mis-decodes without error* (mojibake). The offending README
contained:

| Char | Name             | UTF-8      | Behaviour under cp1252              |
|------|------------------|------------|-------------------------------------|
| `←`  | LEFTWARDS ARROW  | `e2 86 90` | **CRASH** (trailing `0x90`)         |
| `⏰`  | ALARM CLOCK      | `e2 8f b0` | **CRASH** (`0x8f`)                  |
| `量` | CJK 91CF         | `e9 87 8f` | **CRASH** (`0x8f`)                  |
| `—`  | EM DASH (x34)    | `e2 80 94` | silent mojibake `â€"`               |
| `→`  | RIGHTWARDS ARROW | `e2 86 92` | silent mojibake                     |
| `─└├`| box drawing      | `e2 94 ..` | silent mojibake                     |
| `🔥` | FIRE             | `f0 9f 94 a5` | silent mojibake                  |

The `0x90` in `position 2819` was the first of three `←` characters in the diff.

Key insight: **this bug was always present.** Earlier commits that contained em
dashes / arrows were already feeding a *garbled, mis-decoded* diff into Claude —
they just never crashed. This commit was simply the first to include a character
whose UTF-8 encoding hits one of the 5 undefined bytes, converting a silent
corruption bug into a loud crash. The crash is the good outcome: it exposed the
underlying problem.

### Scope: three subprocess boundaries are affected, not one

All three currently rely on `text=True` with no explicit encoding:

| Location                              | Direction              | Failure                                   |
|---------------------------------------|------------------------|-------------------------------------------|
| `run_git()`                           | git stdout -> Python (decode)   | `UnicodeDecodeError` (the observed crash) |
| `call_claude()` `input=user_prompt`   | Python -> claude stdin (encode) | `UnicodeEncodeError` if the prompt has such a char |
| `call_claude()` captured stdout       | claude stdout -> Python (decode)| `UnicodeDecodeError` if the message has such a char |

### Fix

1. Add `encoding="utf-8", errors="replace"` to the `subprocess.run` in
   `run_git()` (line ~32) and in `call_claude()` (line ~98). This covers all
   three boundaries above.
   - `encoding="utf-8"` is the real fix (git and claude both speak UTF-8).
   - `errors="replace"` is defensive: if a repo ever has genuinely non-UTF-8
     bytes in a diff (e.g. a Latin-1 source file), substitute `?` instead of
     crashing. A commit message is a summary, so lossy substitution in an edge
     case is acceptable and far better than the hook dying.

2. **Separate latent issue not covered by (1):** the script's own
   `print(message)` (line ~181) and `print(..., file=sys.stderr)` (error paths
   that embed git's stderr) also use the cp1252 console encoding and will raise
   `UnicodeEncodeError` on Windows if the text contains such a character. (This
   is exactly the failure the diagnostic session hit when printing `->`.) In
   hook mode the message is written via `open(..., encoding="utf-8")`, so the
   primary path is safe, but the stdout/error paths are not. Fix by forcing the
   process's IO to UTF-8, e.g. at startup:
   ```python
   sys.stdout.reconfigure(encoding="utf-8", errors="replace")
   sys.stderr.reconfigure(encoding="utf-8", errors="replace")
   ```
   or by documenting `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` for the hook.

### Deeper root cause / durable fix

The underlying issue is relying on the platform default encoding at any text
boundary. On Windows that is cp1252; Git and modern tooling are UTF-8. Python's
UTF-8 mode (PEP 540, `PYTHONUTF8=1`) exists for exactly this, and Python 3.15 is
slated to make it the default. Being explicit with `encoding="utf-8"` at every
subprocess boundary is the correct fix regardless of interpreter version.

### Verification

Stage a change containing `←` (or any character from the table above) and run
the hook. Before the fix: the `0x90`/`0x8f` traceback. After: a normal generated
commit message.
