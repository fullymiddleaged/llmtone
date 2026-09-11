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

The command exits 1 with `No profile at ... Run `llmtone init` first.`

Do not send them to a terminal. Set it up here:

> I don't have a voice profile for you yet. Point me at a few things you
> actually wrote — paths to files, or just paste them — and I'll build one.
> Work email, messages, notes, posts. Two or three hundred words a tone is
> plenty. **Don't tidy them up first**, that defeats the point.

## Ask before you accept a sample

Two questions, for every file or paste, before any `init` or `analyse` runs.
Ask them out loud. Do not infer the answers and do not run the command until
you have them.

**1. "Did you write this yourself?"**

Not "is this in your voice", not "does this sound like you" — who typed the
words. People offer writing they admire as readily as writing they did, and
an admired README reads exactly like a sample until you ask.

If the answer is no — they admire it, a colleague wrote it, an agent helped
with the repo it came from — it cannot go in the profile, and neither can
part of it. Say that plainly, say why (a borrowed voice becomes their voice
and there is no undoing it), and ask for something they wrote instead. There
is nowhere to file it for later yet; do not invent one, and do not quietly
route it to a scratch profile.

**2. "Which tone is this — business, friendly, marketing, or code?"**

Offer those four words and let them pick. The file's subject does not tell
you: notes to a colleague are `:friendly` even when the topic is work, and a
polished internal doc is `:business` even when nobody outside sees it. If they
describe it rather than label it ("that's how I message people"), read the
label back before you run anything.

One mislabelled sample skews the context it lands in, and contexts feed the
overall average.

## Then build it

Run it yourself with what they gave you, one `--sample` per file, each with the
tone they picked:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python -m llmtone init \
  --sample /path/they/gave.txt:business \
  --sample /another/one.md:friendly
```

Pasted text goes in a file first. This is non-interactive — it asks nothing.

**Never write a sample yourself.** Never rewrite or tidy what they gave you,
and never answer llmtone's onboarding questions on their behalf. A profile
built from your prose and stored under their name is the one outcome this tool
exists to prevent. If they have nothing to hand, say so and leave it — an empty
profile beats a fabricated one.

To add more later: `... -m llmtone analyse FILE --save --context NAME`.

## Making it permanent

If they want the voice available without a tool call, in this project or any
agent that reads `AGENTS.md`:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python -m llmtone prompt --write
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python -m llmtone prompt --write CLAUDE.md
```

It replaces its own block on a rerun, so it is safe to run again after they add
writing. Suggest it; do not run it on a file they have not asked you to touch.
