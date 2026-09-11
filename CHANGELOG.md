# Changelog

Notable changes to llmtone, for people using it.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html). Nothing is released
yet, so everything below is still under Unreleased.

## [Unreleased]

### Added

- `llmtone prompt --write` puts your voice into `AGENTS.md` -- the instructions
  file Codex, Cursor, Copilot, Gemini CLI, Aider, Zed and Claude Code all read
  -- or into any file you name. It splices a marked block, so running it again
  after more writing replaces that block instead of appending a second copy
  below the first. Anything outside the markers is left alone, and a file with
  a half-finished block is refused rather than guessed at.
- A Claude Code plugin, installable with `/plugin marketplace add
  fullymiddleaged/llmtone`. It adds one skill that fetches your profile when
  Claude writes prose for you, and sets up a missing profile with you in the
  conversation rather than sending you to a terminal. Before it accepts any
  sample it asks two things out loud: whether you wrote it yourself, and which
  tone it is. Writing you admire but did not write is refused for the profile,
  and the tone label is yours to pick rather than Claude's to guess.
- [docs/integrations.md](docs/integrations.md) -- which file each tool reads,
  and how to keep the block current.
- `python -m llmtone` runs the whole CLI without installing a console script,
  for agents, MCP servers, CI jobs and plain checkouts. Identical behaviour and
  exit codes to the `llmtone` command.
- `llmtone init` — five questions and a writing sample per tone produce a
  portable `~/.llmtone/profile.json`. It asks for one paste each for business,
  friendly, marketing and code-comment writing, every one of them skippable, so
  a profile has contexts in it from the first run instead of needing them added
  by hand afterwards. `--sample` now repeats and takes a `FILE:CONTEXT` suffix
  (`--sample emails.txt:business`) for a non-interactive run.
- A pasted sample now ends at a line holding a single `.` rather than at the
  first blank line, so writing with paragraphs in it no longer gets cut short
  at the first one.
- A sample too short for its context is kept and says what it is short by,
  rather than disappearing into the overall profile without comment.
- `llmtone prompt --context NAME` for a context you have no writing for now
  offers to start it from a paste there and then, instead of only telling you
  the context does not exist. It stays an error when nobody is at the terminal,
  and a paste too short to establish the context says so rather than inventing
  one: llmtone still reports only tones it has actually seen you write.
- `llmtone calibrate` — asks about whatever your profile is least sure of
  rather than a fixed list, so a second session is not a repeat of the first.
  `-n` sets how many questions, `--dry-run` shows what it would ask and why,
  `--answers FILE` runs it non-interactively.
- A/B word choices in `llmtone calibrate` — pick between "utilise" and "use",
  and the `avoid` list becomes evidence instead of a guess about words you
  happen not to have written. `--pairs` sets how many, `--choices FILE` scripts
  them.
- `notes.avoid_confirmed_by_choice` in the profile: the `avoid` entries you
  chose against, which a consumer may enforce strictly. The rest are still
  guesses, and `notes.avoid_inferred_from_absence` still says so.
- Contradiction detection in `llmtone profile` — when your samples disagree
  about a dimension by more than 30 points, it names the dimension and shows
  the range ("Formality 13-85 across samples") instead of reporting only the
  average. That is context, not error — label your samples and it splits them.
- `notes.varies_by_context` in the profile: the same list, as
  `{dimension, low, high, scatter}`, for tools that want to weight those
  dimensions loosely. An empty array means the check found nothing.
- `--context LABEL` on `llmtone analyse --save` — say where a sample was
  written and that context gets its own profile, shown in `llmtone profile` as
  its shift from your overall voice. Contexts often read as *more* confident
  than the overall profile, because samples that contradict each other pooled
  agree once they are split.
- `llmtone prompt --context work` — instructions for how you write in one
  context, falling back to your overall voice for anything that context has no
  evidence about.
- `llmtone analyse FILE` — metrics for one file. `--json` for everything,
  `--save` to add the file to your profile.
- `llmtone profile` — your profile as bars and prose, with a confidence per
  dimension. Anything under 0.45 confidence is reported as not yet established.
- `llmtone prompt` — model-independent writing instructions for any AI tool.
- `llmtone export` — the profile as JSON, to stdout or `-o FILE`.
- `voice-profile.json` schema 1.0, published as `voice-profile.schema.json` for
  other tools to read and write.

### Notes

- Confidence can *fall* after calibrating. Answers that disagree with your
  existing samples lower it, which is the honest result rather than a fault —
  see [docs/scoring.md](docs/scoring.md).
- Nothing leaves your machine: this version contains no network code at all.
  See [docs/privacy.md](docs/privacy.md).
