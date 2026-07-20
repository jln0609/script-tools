#!/usr/bin/env python3
"""Generate a git commit message for staged changes using Claude Code (`claude -p`)."""

import argparse
import os
import re
import shutil
import subprocess
import sys

DEFAULT_MAX_DIFF_CHARS = 12000
DEFAULT_MAX_BUDGET_USD = "0.50"

# The commit-message rules live in this subagent, which install_hook.py copies
# into the target repo's .claude/agents/ so Claude Code discovers it by name;
# we run the `claude` session *as* that agent rather than duplicating the
# prompt here. See commit-message-writer.md for the source of truth.
AGENT_NAME = "commit-message-writer"

USER_PROMPT_TEMPLATE = """Recent commit messages in this repo (newest first, for style reference):
{recent_log}

Files changed (staged):
{stat}

Staged diff{diff_note}:
{diff}
"""


def run_git(args, cwd):
    result = subprocess.run(
        ["git", "-C", cwd] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("git {} failed: {}".format(" ".join(args), result.stderr.strip()))
    return result.stdout


def get_repo_root(path):
    return run_git(["rev-parse", "--show-toplevel"], path).strip()


def get_staged_diff(repo):
    return run_git(["diff", "--cached", "--no-color"], repo)


def get_staged_stat(repo):
    return run_git(["diff", "--cached", "--stat", "--no-color"], repo)


def get_recent_log(repo, count=10):
    try:
        return run_git(["log", "-{}".format(count), "--pretty=format:- %s"], repo)
    except RuntimeError:
        return ""


def truncate_diff(diff, max_chars):
    if len(diff) <= max_chars:
        return diff, False
    return diff[:max_chars], True


def build_user_prompt(repo, max_chars):
    diff = get_staged_diff(repo)
    if not diff.strip():
        return None
    stat = get_staged_stat(repo).strip()
    recent_log = get_recent_log(repo).strip() or "(no commit history yet)"
    diff, truncated = truncate_diff(diff, max_chars)
    diff_note = " (truncated, showing first {} characters)".format(max_chars) if truncated else ""
    return USER_PROMPT_TEMPLATE.format(recent_log=recent_log, stat=stat, diff=diff, diff_note=diff_note)


def call_claude(user_prompt, model=None, max_budget_usd=DEFAULT_MAX_BUDGET_USD, timeout=120):
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError("claude CLI not found on PATH. Install Claude Code first.")

    # Run the session *as* the commit-message-writer agent. Claude Code loads
    # its prompt, model, and tool restrictions from the agent file that
    # install_hook.py placed in the repo's .claude/agents/; if it can't resolve
    # the name, `claude` errors and we surface that below.
    cmd = [
        claude_bin, "-p",
        "--output-format", "text",
        "--agent", AGENT_NAME,
        "--no-session-persistence",
        "--max-budget-usd", str(max_budget_usd),
    ]
    if model:
        cmd += ["--model", model]

    try:
        result = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude -p timed out after {}s".format(timeout))

    if result.returncode != 0:
        raise RuntimeError("claude -p failed: {}".format(result.stderr.strip() or result.stdout.strip()))
    return result.stdout.strip()


def clean_message(text):
    text = text.strip()
    fence_match = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def write_commit_msg_file(path, message):
    original = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()
    comment_lines = [line for line in original.splitlines(keepends=True) if line.startswith("#")]
    with open(path, "w", encoding="utf-8") as f:
        f.write(message + "\n")
        if comment_lines:
            f.write("\n")
            f.writelines(comment_lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.getcwd(), help="Path inside the git repo (default: cwd)")
    parser.add_argument("--file", help="Write the message into this file instead of stdout (used by the prepare-commit-msg hook)")
    parser.add_argument("--max-diff-chars", type=int, default=DEFAULT_MAX_DIFF_CHARS)
    parser.add_argument("--max-budget-usd", default=DEFAULT_MAX_BUDGET_USD, help="Cap on API spend for this call")
    parser.add_argument("--model", help="Override the Claude model used")
    parser.add_argument("--commit", action="store_true", help="Run 'git commit' with the generated message (asks for confirmation unless --yes)")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt when used with --commit")
    parser.add_argument("--quiet", action="store_true", help="Suppress non-essential stderr output (used by the hook)")
    args = parser.parse_args()

    try:
        repo = get_repo_root(args.repo)
    except RuntimeError as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1

    try:
        user_prompt = build_user_prompt(repo, args.max_diff_chars)
    except RuntimeError as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1

    if user_prompt is None:
        if not args.quiet:
            print("No staged changes to generate a commit message from.", file=sys.stderr)
        return 1

    try:
        raw = call_claude(user_prompt, model=args.model, max_budget_usd=args.max_budget_usd)
    except RuntimeError as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1

    message = clean_message(raw)
    if not message:
        print("error: claude returned an empty message", file=sys.stderr)
        return 1

    if args.file:
        write_commit_msg_file(args.file, message)
        if not args.quiet:
            print("Wrote generated commit message to {}".format(args.file), file=sys.stderr)
    else:
        print(message)

    if args.commit:
        if not args.yes:
            print("\n--- Generated commit message ---\n{}\n---------------------------------".format(message))
            answer = input("Commit with this message? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted.", file=sys.stderr)
                return 1
        commit_result = subprocess.run(["git", "-C", repo, "commit", "-m", message])
        return commit_result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
