# llmtone

### One voice. Any AI.

llmtone is an open-source, local-first personal writing profile for AI.

It analyses how you actually write. It asks a small number of questions to
settle what your writing alone cannot. The result is a portable profile you can
use with Claude Code, Codex, Gemini, local models and anything else.

Your voice stays yours.

```
                    your writing
                         │
                         ▼
                      llmtone
                         │
                         ▼
                 voice-profile.json
                         │
        ┌────────────┬───┴────────┬────────────┐
        ▼            ▼            ▼            ▼
     Claude        Codex       Gemini     local model
```

> **Status: Phase 2.** The analyser, scoring engine, profile format, CLI,
> calibration, per-context profiles and the agent integrations work. Voice
> checking, a PyPI release and an MCP server are next. See
> [Roadmap](#roadmap).

---

## Why

Every AI tool has its own idea of style settings, and none of them are
portable. "Write like me" is a prompt you rewrite from scratch in every new
tool. Your writing voice is yours, but it ends up scattered across half a dozen
products that each own a fragment of it.

llmtone makes it a file.

Phase 1 has no network code at all. Not disabled, absent. There is no account,
no database and no embeddings, just plain JSON in `~/.llmtone/`. The same
writing produces the same profile every time, on every machine. Every score
comes from weighted rules you can read in one file and change in one line. The
profile describes writing rather than prompts, so it does not assume which
model you use. It needs Python and nothing else.

It is not an AI humanizer, not an AI detector, and not a personality model. It
describes writing behaviour, and says so in the output.

---

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/fullymiddleaged/llmtone
cd llmtone
pip install -e .
```

Or straight from GitHub, without a checkout:

```bash
pip install git+https://github.com/fullymiddleaged/llmtone
```

That puts an `llmtone` command on your PATH. You may prefer to install nothing
at all. You may also be driving llmtone from an agent, an MCP server or a CI
job, where a generated executable on the PATH is a nuisance. Run the module
instead. It behaves identically and works straight out of a checkout:

```bash
python -m llmtone init
python -m llmtone prompt --context business
```

Every `llmtone ...` below can be read as `python -m llmtone ...`.

## Use

```bash
llmtone init
```

Five questions come first. They ask about your job, something you are into, a
disagreement, a recent annoyance and something you are good at. None of them
ask you to describe your writing style, because nobody is a reliable witness to
their own prose.

Then it asks for something you have actually written, once per tone. The tones
are work, friendly, marketing and code comments. Skip any you do not write in.
**Do not rewrite them first.**

Each paste ends at a line with a single `.` on it, so multi-paragraph writing
survives intact. About 200 words a tone, two or three emails, earns that tone a
profile of its own. Anything shorter still counts towards your overall voice,
and llmtone says how far short it was rather than dropping it silently.

A tone you skipped is simply not there. llmtone reports writing it has seen and
nothing else. So `llmtone prompt --context marketing` with no marketing samples
does not invent one. It offers to start that context from a paste, there and
then.

```
$ llmtone profile

Your Voice Profile

  Formality           20  ██░░░░░░░░  conf 0.69 ?
  Directness          59  ██████░░░░  conf 0.58 ?
  Warmth              39  ████░░░░░░  conf 0.58 ?
  Conciseness         79  ████████░░  conf 0.56 ?
  Humour              19  ██░░░░░░░░  conf 0.25 ??
  Hedging             33  ███░░░░░░░  conf 0.49 ?
  Technicality        38  ████░░░░░░  conf 0.53 ?
  Conversationality   63  ██████░░░░  conf 0.74

  Samples analysed: 6
  Words analysed:   473

  ? low confidence   ?? not yet established

You're very casual, reasonably direct and matter-of-fact.
You use contractions naturally, your sentences average about 10 words with some
variation in length and your paragraphs are short.
You never use: ellipses, em dashes, en dashes, exclamation marks, parentheses,
question marks and semicolons.
Not yet confident about: humour. More writing, or the calibration questions,
will settle these.
```

Six samples and 473 words is not much, and the profile says so. Most dimensions
are marked low-confidence, and humour is flagged as not established at all.
Feed it more writing and the confidences climb.

Feed it writing from two different worlds and it says that instead:

```
  You write very differently in different places
    Formality          13-85 across samples
    Hedging            18-78 across samples
    Conversationality  8-65 across samples
    and 2 more: technicality, conciseness
  That is context, not error -- but the single value above is an average of both.
  Split them with: llmtone analyse FILE --save --context work
```

Your work email and your messages to friends are not the same voice, and one
number in the middle describes neither. llmtone reports the range rather than
quietly averaging it away.

Tell it which is which and it stops averaging them at all:

```
$ llmtone analyse work-email.md --save --context work
$ llmtone profile

  How that shifts by context
    friends  (1 sample, 352 words)
      Conversationality   71  +30 vs overall
      Technicality        28  -25 vs overall
    work  (2 samples, 862 words)
      Formality           82  +32 vs overall
      Conversationality   10  -31 vs overall
      and 4 more
  Write for one of these with: llmtone prompt --context NAME
```

Contexts usually come out more confident than the overall profile. Samples that
contradict each other when pooled agree once they are split by where you wrote
them. Labels are yours to choose, and llmtone will not guess them.

Then hand your voice to any model:

```bash
llmtone prompt
```

```
Write in this person's voice. Their observed habits:

- Very casual.
- Reasonably direct.
- Matter-of-fact.
- Concise.
- Rarely hedges.
- Lightly technical.
- Conversational.
- Sentences average around 10 words. Keep their length fairly even.
- Use contractions naturally.
- Occasional sentence fragments are in character.
- Prefer active voice.
- Keep paragraphs short.
- Use few or no headings.
- Do not use: ellipses, em dashes, en dashes, exclamation marks, parentheses,
  question marks and semicolons.
- Vocabulary they reach for: definitely, rather.
- Domain vocabulary they use without explaining: logs, deployment, pipeline.

Constraints:
- Do not imitate or copy any source text literally.
- Do not add introductions or conclusions that were not asked for.
- The result should read as naturally written, not polished into uniformity.
- These are writing habits, not personality traits. Do not role-play a persona.
```

Note that humour is missing from those instructions. It scored 19, but at 0.25
confidence llmtone will not assert it. A dimension below 0.45 is left out
entirely rather than passed to a model as if it were known.

Reproduce exactly this with:

```bash
llmtone init --answers examples/answers.json \
             --sample tests/fixtures/casual_direct.txt
```

`--sample` repeats, and a `:CONTEXT` suffix labels the file. A whole set of
tones can be onboarded in one non-interactive command:

```bash
llmtone init --sample emails.txt:business \
             --sample chat.txt:friendly \
             --sample launch-post.md:marketing
```

Pipe it wherever you like:

```bash
llmtone prompt | pbcopy
llmtone export -o voice-profile.json
```

## Use it with your agent

Most coding agents read a markdown file for standing instructions. Put your
voice in it:

```bash
llmtone prompt --write
```

That splices a marked block into `AGENTS.md`, which is read natively by Codex,
Cursor, Copilot, Gemini CLI, Aider, Zed and Claude Code. `--write CLAUDE.md`
puts it in CLAUDE.md instead, and `--context work` writes the voice for one
context.

```markdown
# My project

Build with make.

<!-- llmtone:start -->
## Writing voice
...
<!-- llmtone:end -->
```

Run it again after `llmtone calibrate` and it **replaces** that block. Anything
outside the markers is yours and is never touched. That is the whole reason for
the flag. `llmtone prompt >> AGENTS.md` leaves last month's profile sitting
above this month's, and a file holding two of them describes neither.

For Claude Code there is also a plugin, so the voice is available without a
file at all:

```
/plugin marketplace add fullymiddleaged/llmtone
/plugin install llmtone@llmtone
```

It adds one skill that fetches your profile when Claude writes prose for you.
If you have no profile it tells you to run `llmtone init` yourself rather than
answering the questions on your behalf. An agent inventing your voice is the
one thing this tool exists to prevent.

More in [docs/integrations.md](docs/integrations.md).

## Commands

| Command | |
|---|---|
| `llmtone init` | Five questions, then one writing sample per tone: business, friendly, marketing, code. `--sample FILE:CONTEXT` repeats for a non-interactive run. |
| `llmtone analyse FILE` | Metrics for one file. `--json` for everything, `--save` to add it to your profile. |
| `llmtone profile` | Your profile, as bars and prose. |
| `llmtone prompt` | Model-independent writing instructions. `--write [FILE]` splices them into `AGENTS.md`, replacing what an earlier run put there. |
| `llmtone export` | The profile as JSON. |
| `llmtone calibrate` | More questions, chosen by whatever the profile is least sure of, plus a couple of A/B word choices. `-n` and `--pairs` set how many of each, `--dry-run` shows what it would ask. |
| `llmtone check FILE` | Phase 3. |

Add more writing at any time. The profile gets better as it sees more:

```bash
llmtone analyse --save ~/notes/some-real-email.txt
```

Or let it ask. `llmtone calibrate` looks at which dimensions are least settled
and picks questions aimed at those, so the second session is not a repeat of
the first:

```
$ llmtone calibrate --dry-run

Chasing: hedging (conf 0.49), conciseness (conf 0.56), directness (conf 0.58)

Would ask 3:

  Your manager asks for something on a timeline you think is unrealistic.
  Write your reply.
    for: hedging, directness, formality
  ...
```

Answers are analysed exactly like any other writing. The selection decides which
question you see, never what the answer scores.

It also offers a few straight choices:

```
Which of these would you actually write?
  1) utilise
  2) use
  [1, 2, n for neither, Enter to skip]
```

That is what makes the `avoid` list worth anything. Without it, llmtone can only
notice that you have never written "utilise" in 400 words and guess. One
keystroke turns the guess into evidence. The generated prompt then says
`never use` for the words you chose against, and `probably avoid` for the rest.

## Your data

```
~/.llmtone/
├── profile.json      your derived profile
├── evidence.jsonl    one record per answer or sample
└── samples/          your writing, exactly as you gave it
```

Plain text. Read it, edit it, delete it, keep it in a private repo. Set
`LLMTONE_HOME` to put it somewhere else.

The evidence log is the source of truth. `profile.json` is derived from it and
can be rebuilt at any time. That is what makes a future scoring improvement
re-score everything you have already written, rather than asking you to answer
the questions again.

Full detail in [docs/privacy.md](docs/privacy.md).

## How the scoring works

Eight dimensions, each a weighted sum of observable features. They are
formality, directness, warmth, conciseness, humour, hedging, technicality and
conversationality.

```python
weights = {
    "contraction_rate":       -0.22,
    "formal_vocab_rate":       0.20,
    "colloquial_rate":        -0.18,
    "avg_sentence_length":     0.12,
    "formal_transition_rate":  0.10,
    "long_word_rate":          0.10,
    "first_person_rate":      -0.08,
}
```

That is the whole of formality. No model, no training, no hidden layer. Every
weight lives in [`llmtone/scoring/dimensions.py`](llmtone/scoring/dimensions.py)
and every word list in
[`llmtone/analysis/lexicons.py`](llmtone/analysis/lexicons.py). Disagree with a
score, change a number, rerun.

Each dimension also carries a confidence, and llmtone is deliberately honest
about what it cannot know. **Humour is capped at 0.55**, because counting
exclamation marks does not tell you whether someone is funny. Anything below
0.45 is reported as not yet established and left out of the generated
instructions entirely.

Three metrics stand in for a parser: passive voice, sentence fragments and
subordinate clauses. They are flagged as approximate everywhere they appear,
and [docs/metrics.md](docs/metrics.md) spells out exactly how each one is wrong.

- [docs/scoring.md](docs/scoring.md): how evidence becomes a score
- [docs/metrics.md](docs/metrics.md): every metric and its limits
- [docs/schema.md](docs/schema.md): the profile format
- [docs/privacy.md](docs/privacy.md): what is stored and what leaves
- [docs/integrations.md](docs/integrations.md): getting it into your tools

## The profile format

[`voice-profile.schema.json`](voice-profile.schema.json) is published openly so
other tools can read and write this format without depending on llmtone. The
goal is a portable format you own, not a file only one program understands.

```json
{
  "version": "1.0",
  "style": {
    "formality":  { "value": 20, "confidence": 0.69 },
    "directness": { "value": 59, "confidence": 0.58 }
  },
  "syntax":      { "average_sentence_length": 9.65, "contraction_preference": 0.946 },
  "punctuation": { "semicolon": "never", "em_dash": "never", "comma": "occasional" },
  "vocabulary":  { "prefer": ["definitely", "rather"], "avoid": ["leverage"] },
  "structure":   { "paragraph_length": "short", "bullet_preference": "medium" }
}
```

A complete generated profile is at
[examples/example-profile.json](examples/example-profile.json), and the format
is documented in [docs/schema.md](docs/schema.md).

## Roadmap

**Phase 1 is done.** Text analyser, profile schema, deterministic scoring, CLI,
onboarding, writing-sample analysis, prompt renderer.

**Phase 2 is done.** Adaptive question selection, the A/B word-choice library
behind `llmtone calibrate`, contradiction detection and per-context profiles.

**Phase 3.** Integration. `llmtone prompt --write` and the Claude Code plugin
are done. Still to come is `llmtone check`, a personal-style consistency checker
that is explicitly not an AI detector. Then learning from your edits, a PyPI
release so `uvx llmtone` works with nothing installed, and an MCP server.

**Phase 4.** Optional LLM providers for question wording only, never for
scoring, and an optional local web UI.

The scoring engine is meant to improve. The profile format is versioned and
independent of it, so better scoring will not mean a new format.

## Contributing

The most useful contributions right now are disagreements with the numbers. If
a score is wrong for your writing, the fix is usually a word list or a weight,
and both are one file each.

```bash
pip install -e . && python -m pytest
```

Tests assert relative outcomes rather than exact values. The formal fixture
scores higher on formality than the casual one. Retuning the weights therefore
does not mean rewriting the suite.

## Licence

MIT. See [LICENSE](LICENSE).
