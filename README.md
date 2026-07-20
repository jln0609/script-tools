# script-tools

A collection of small, self-contained developer scripts and tools. Each tool
lives in its own directory with its own README covering setup and usage; there
are no shared dependencies between them, so you can copy any one out and use it
on its own.

## Tools

- **[commit-message-generator](commit-message-generator/)** — Generates git
  commit messages from the staged diff using Claude Code (`claude -p`). Runs
  standalone or as a `prepare-commit-msg` hook that pre-fills the commit
  editor. See its [README](commit-message-generator/README.md) for setup.

## Layout

```
script-tools/
└── commit-message-generator/   # git commit message generator (Claude Code)
```

Each new tool gets its own top-level directory and a README of its own.
