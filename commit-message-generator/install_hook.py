#!/usr/bin/env python3
"""Install a prepare-commit-msg hook that generates commit messages via Claude Code.

Usage:
    python install_hook.py [--repo PATH] [--force]

Installs into the target repo's real hooks directory (resolved with
`git rev-parse --git-path hooks`, so it works correctly for worktrees too).
"""

import argparse
import os
import stat
import subprocess
import sys

MARKER = "# Installed by script-tools commit-message-generator"

HOOK_TEMPLATE = """#!/bin/sh
{marker} - do not edit by hand, rerun install_hook.py to update1/reinstall.
COMMIT_MSG_FILE="$1"
COMMIT_SOURCE="$2"

# Only generate a message for a plain `git commit` with no -m/-c/-C/-t and no
# merge/squash source; anything else already has (or will get) its own message.
if [ -n "$COMMIT_SOURCE" ]; then
  exit 0
fi

GENERATOR="{generator_path}"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

# Never block a commit if generation fails (no `claude` on PATH, network down, etc.) -
# git just falls back to its normal empty-template editor experience.
"$PY" "$GENERATOR" --file "$COMMIT_MSG_FILE" --quiet
exit 0
"""


def get_hooks_dir(repo):
    result = subprocess.run(
        ["git", "-C", repo, "rev-parse", "--git-path", "hooks"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("not a git repo: {}".format(repo))
    hooks_dir = result.stdout.strip()
    if not os.path.isabs(hooks_dir):
        hooks_dir = os.path.join(repo, hooks_dir)
    return hooks_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.getcwd(), help="Target git repo to install the hook into (default: cwd)")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing prepare-commit-msg hook not installed by this tool")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    generator_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_commit_message.py")

    try:
        hooks_dir = get_hooks_dir(repo)
    except RuntimeError as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1

    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "prepare-commit-msg")

    if os.path.exists(hook_path):
        with open(hook_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARKER not in existing and not args.force:
            print("error: {} already exists and wasn't installed by this tool. Use --force to overwrite.".format(hook_path), file=sys.stderr)
            return 1

    content = HOOK_TEMPLATE.format(marker=MARKER, generator_path=generator_path.replace("\\", "/"))
    with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    try:
        st = os.stat(hook_path)
        os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass

    print("Installed prepare-commit-msg hook at {}".format(hook_path))
    print("It runs: <python3|python> {} --file <msg-file> --quiet".format(generator_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
