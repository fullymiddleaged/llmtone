# Changelog

Notable changes to llmtone, for people using it.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html). Nothing is released
yet, so everything below is still under Unreleased.

## [Unreleased]

### Added

- `llmtone init` — five questions and one real writing sample produce a
  portable `~/.llmtone/profile.json`.
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
