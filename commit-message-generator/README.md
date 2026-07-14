# commit-message-generator

Generates git commit messages from the staged diff using Claude Code (`claude -p`).

## Standalone use (any repo)

```sh
git add <files>
python /path/to/commit-message-generator/generate_commit_message.py
```

Prints the generated message to stdout. Useful flags:

- `--repo PATH` — run against a different repo (default: cwd)
- `--commit` — after generating, ask for confirmation and run `git commit -m "<message>"` (add `--yes` to skip the prompt)
- `--model NAME` — override the Claude model
- `--max-diff-chars N` — cap how much of the diff is sent (default 12000)
- `--max-budget-usd N` — cap API spend for the call (default 0.50)

## Install as a git hook (auto-fill on `git commit`)

```sh
python /path/to/commit-message-generator/install_hook.py --repo /path/to/target/repo
```

Installs a `prepare-commit-msg` hook that pre-fills the commit message editor
whenever you run a plain `git commit` (no `-m`, not a merge/squash/amend with
an existing message). Re-run with `--force` to reinstall/update. If generation
fails for any reason (`claude` not on PATH, no network, etc.) it silently
falls back to git's normal empty template — it never blocks a commit.

Requires the `claude` CLI to be installed and logged in, and `python3` (or
`python`) on `PATH` inside the target repo's shell environment.
