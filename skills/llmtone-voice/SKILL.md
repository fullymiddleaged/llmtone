---
name: llmtone-voice
description: Write in the user's own voice. Use when drafting, rewriting or editing prose on their behalf — emails, docs, READMEs, release notes, commit messages, posts, replies — or when they mention their writing voice, tone, style, or llmtone.
allowed-tools:
  - Bash
---

# Write in their voice

The user has a local writing profile built from writing they actually did.
Fetch it and follow it, rather than guessing at their style.

## Get the instructions

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python -m llmtone prompt
```

This plugin ships llmtone itself, and llmtone imports nothing outside the
standard library, so that runs whether or not the user has installed anything.
If `python` is not found, try `python3` or `py`.

Do not reach for a bare `llmtone` command. It only exists if they installed the
package separately, and on Windows the executable pip generates for it is
frequently blocked from running.

If they named a context — work, friendly, marketing, code — add `--context NAME`.
`... -m llmtone profile` lists the contexts they have.

Fetch it once per session and reuse it. It only changes when they add writing.

## Apply it

The output is a list of observed writing habits. Follow them for prose you
write on their behalf. Three things it is not:

- **Not a persona.** These are habits, not personality. Do not role-play a
  character, do not perform a mood.
- **Not for code.** It governs prose — docs, comments, commit bodies, messages.
  Code style comes from the codebase.
- **Not a licence to copy.** Never reproduce phrasing from their samples.

Anything the profile does not assert, it does not know. It deliberately leaves
out dimensions it is not yet confident about; do not fill those gaps by
inventing a trait.

## When there is no profile

The command exits 1 and says:

```
No profile at ~/.llmtone/profile.json. Run `llmtone init` first.
```

**Stop and tell them to run `llmtone init` in their own terminal.** Do not run
it yourself.

`init` asks five questions about their life and asks them to paste writing they
did. Answering it on their behalf would fabricate a voice out of your own
prose and store it as theirs — which is the one thing this tool exists to
prevent. It is interactive by design. Hand it back to them:

> You don't have a voice profile yet. Run `llmtone init` in your terminal (or
> `python -m llmtone init` from a checkout) — five questions and a writing
> sample per tone, about five minutes — then ask me again.

## Making it permanent

If they want the voice available without a tool call, in this project or any
agent that reads `AGENTS.md`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python -m llmtone prompt --write
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python -m llmtone prompt --write CLAUDE.md
```

It replaces its own block on a rerun, so it is safe to run again after they add
writing. Suggest it; do not run it on a file they have not asked you to touch.
