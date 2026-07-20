# commit-message-generator

Generates git commit messages from the staged diff using Claude Code (`claude -p`).

The generator runs the `claude` session as the `commit-message-writer`
subagent (see `.claude/agents/commit-message-writer.md`, the single source of
truth for the message rules). Claude Code discovers that agent by name, so the
agent file must live where Claude Code looks — the target repo's
`.claude/agents/` — which `install_hook.py` sets up for you (see below).

## Standalone use

```sh
python /path/to/commit-message-generator/install_hook.py --repo /path/to/repo  # once, installs the agent
git add <files>
python /path/to/commit-message-generator/generate_commit_message.py --repo /path/to/repo
```

Prints the generated message to stdout. Running the generator in a repo where
the agent hasn't been installed fails with a "agent not found" error from
`claude` — install first (or copy the agent into that repo's `.claude/agents/`).
Useful flags:

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
an existing message). It also copies `commit-message-writer.md` into the
target repo's `.claude/agents/` so Claude Code can resolve the agent by name.
Re-run with `--force` to reinstall/update. If generation fails for any reason
(`claude` not on PATH, no network, etc.) it silently falls back to git's normal
empty template — it never blocks a commit.

The hook lives in `.git/hooks/` (untracked), but the agent file lands in the
tracked working tree at `.claude/agents/commit-message-writer.md`. Commit it so
teammates share the agent, or add it to `.gitignore` / `.git/info/exclude` to
keep it local — the installer prints a reminder either way.

Requires the `claude` CLI to be installed and logged in, and `python3` (or
`python`) on `PATH` inside the target repo's shell environment.
