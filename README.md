# llmtone

### One voice. Any AI.

llmtone is an open-source, local-first personal writing profile for AI.

It analyses how you actually write, asks a small number of questions to resolve
what it can't tell from your writing alone, and builds a portable profile you can
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

> **Status: Phase 1.** The analyser, scoring engine, profile format, CLI and
> prompt renderer work. Adaptive calibration, voice checking and the MCP server
> are next — see [Roadmap](#roadmap).

---

## Why

Every AI tool has its own idea of "style settings", none of them portable, and
"write like me" is a prompt you rewrite from scratch in every new tool. Your
writing voice is yours, but it ends up scattered across half a dozen products
that each own a fragment of it.

llmtone makes it a file.

- **Local-first.** Phase 1 has no network code at all. Not disabled — absent.
- **No account, no database, no embeddings.** Plain JSON in `~/.llmtone/`.
- **Deterministic.** The same writing produces the same profile, every time, on
  every machine.
- **Inspectable.** Every score comes from weighted rules you can read in one
  file and change in one line.
- **Model-independent.** The profile describes writing, not prompts. It does not
  assume which model you use.
- **Zero dependencies.** Python and nothing else.

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

That puts an `llmtone` command on your PATH. If you would rather not install
anything -- or you are driving llmtone from an agent, an MCP server or a CI
job, where a generated executable on the PATH is a nuisance -- run the module
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

Five questions — about your job, something you're into, a disagreement, a recent
annoyance, something you're good at. None of them ask you to describe your
writing style, because nobody is a reliable witness to their own prose.

Then it asks for something you've actually written, once per tone: work,
friendly, marketing, code comments. Skip any you don't write in. **Don't
rewrite them first.**

Each paste ends at a line with a single `.` on it, so multi-paragraph writing
survives intact. About 200 words a tone -- two or three emails -- before that
tone gets a profile of its own; anything shorter still counts towards your
overall voice, and llmtone says how far short it was rather than dropping it
silently.

A tone you skipped is simply not there. llmtone reports writing it has seen and
nothing else, so `llmtone prompt --context marketing` with no marketing samples
does not invent one -- it offers to start that context from a paste, there and
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

Six samples and 473 words is not much, and the profile says so: most dimensions
are marked low-confidence, and humour is flagged as not established at all. Feed
it more writing and the confidences climb.

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

Contexts usually come out *more* confident than the overall profile: samples
that contradict each other pooled agree once they are split by where you wrote
them. Labels are yours to choose — llmtone will not guess them.

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
confidence llmtone won't assert it — a dimension below 0.45 is left out
entirely rather than passed to a model as if it were known.

Reproduce exactly this with:

```bash
llmtone init --answers examples/answers.json \
             --sample tests/fixtures/casual_direct.txt
```

`--sample` repeats, and a `:CONTEXT` suffix labels the file -- so a whole set of
tones can be onboarded in one non-interactive command:

```bash
llmtone init --sample emails.txt:business \
             --sample chat.txt:friendly \
             --sample launch-post.md:marketing
```

Pipe it wherever you like:

```bash
llmtone prompt >> CLAUDE.md
llmtone prompt | pbcopy
llmtone export -o voice-profile.json
```

## Commands

| Command | |
|---|---|
| `llmtone init` | Five questions, then one writing sample per tone (business, friendly, marketing, code). `--sample FILE:CONTEXT` repeats for a non-interactive run. |
| `llmtone analyse FILE` | Metrics for one file. `--json` for everything, `--save` to add it to your profile. |
| `llmtone profile` | Your profile, as bars and prose. |
| `llmtone prompt` | Model-independent writing instructions. |
| `llmtone export` | The profile as JSON. |
| `llmtone calibrate` | More questions, chosen by whatever the profile is least sure of, plus a couple of A/B word choices. `-n` and `--pairs` set how many of each, `--dry-run` shows what it would ask. |
| `llmtone check FILE` | Phase 3. |

Add more writing at any time — the profile gets better as it sees more:

```bash
llmtone analyse --save ~/notes/some-real-email.txt
```

Or let it ask. `llmtone calibrate` looks at which dimensions are least settled
and picks questions aimed at those, so the second session is not a repeat of the
first:

```
$ llmtone calibrate --dry-run

Chasing: hedging (conf 0.49), conciseness (conf 0.56), directness (conf 0.58)

Would ask 3:

  Your manager asks for something on a timeline you think is unrealistic.
  Write your reply.
    for: hedging, directness, formality
  ...
```

Answers are analysed exactly like any other writing — the selection decides
*which question you see*, never what the answer scores.

It also offers a few straight choices:

```
Which of these would you actually write?
  1) utilise
  2) use
  [1, 2, n for neither, Enter to skip]
```

That is what makes the `avoid` list worth anything. Without it, llmtone can only
notice that you have never written "utilise" in 400 words and guess. One
keystroke turns the guess into evidence, and the generated prompt says *never
use* for the words you chose against and *probably avoid* for the rest.

## Your data

```
~/.llmtone/
├── profile.json      your derived profile
├── evidence.jsonl    one record per answer or sample
└── samples/          your writing, exactly as you gave it
```

Plain text. Read it, edit it, delete it, keep it in a private repo. Set
`LLMTONE_HOME` to put it somewhere else.

The evidence log is the source of truth; `profile.json` is derived from it and
can be rebuilt at any time. That is what makes a future scoring improvement
re-score everything you have already written, rather than asking you to answer
the questions again.

Full detail in [docs/privacy.md](docs/privacy.md).

## How the scoring works

Eight dimensions — formality, directness, warmth, conciseness, humour, hedging,
technicality, conversationality — each a weighted sum of observable features:

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
about what it cannot know: **humour is capped at 0.55**, because counting
exclamation marks does not tell you whether someone is funny. Anything below
0.45 is reported as "not yet established" and left out of the generated
instructions entirely.

Three metrics — passive voice, sentence fragments, subordinate clauses — are
heuristics standing in for a parser. They are flagged as approximate everywhere
they appear, and [docs/metrics.md](docs/metrics.md) spells out exactly how each
one is wrong.

- [docs/scoring.md](docs/scoring.md) — how evidence becomes a score
- [docs/metrics.md](docs/metrics.md) — every metric and its limits
- [docs/schema.md](docs/schema.md) — the profile format
- [docs/privacy.md](docs/privacy.md) — what is stored and what leaves

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

**Phase 1 — done.** Text analyser, profile schema, deterministic scoring, CLI,
onboarding, writing-sample analysis, prompt renderer.

**Phase 2 — done.** Adaptive question selection, the A/B word-choice library
(`llmtone calibrate`), contradiction detection and per-context profiles.

**Phase 3.** `llmtone check` (a personal-style consistency checker — explicitly
*not* an AI detector), learning from your edits, MCP server, integration docs.

**Phase 4.** Optional LLM providers for question wording only — never for
scoring — and an optional local web UI.

The scoring engine is meant to improve. The profile format is versioned and
independent of it, so better scoring will not mean a new format.

## Contributing

The most useful contributions right now are disagreements with the numbers. If
a score is wrong for your writing, the fix is usually a word list or a weight,
and both are one file each.

```bash
pip install -e . && python -m pytest
```

Tests assert *relative* outcomes — the formal fixture scores higher on formality
than the casual one — rather than exact values, so retuning the weights doesn't
mean rewriting the suite.

## Licence

MIT. See [LICENSE](LICENSE).
