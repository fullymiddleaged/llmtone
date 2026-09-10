# Scoring

How llmtone gets from "you used 8 contractions" to "conversationality: 71".

The whole point of this design is that you can read it. If a score looks wrong,
you should be able to find out why in a couple of minutes, and change it.

---

## The pipeline

```
evidence  →  analysis  →  scoring  →  profile  →  prompt
 what you    observable   weighted    portable    instructions
 wrote       metrics      rules       JSON        for a model
```

Each arrow is a pure function. Each stage is inspectable on its own:

| Stage | Where it lives | How to look at it |
|---|---|---|
| evidence | `~/.llmtone/evidence.jsonl` + `samples/` | `cat` it |
| analysis | `llmtone/analysis/` | `llmtone analyse --json FILE` |
| scoring | `llmtone/scoring/` | `DimensionResult.explain()` |
| profile | `~/.llmtone/profile.json` | `llmtone profile` |
| prompt | `llmtone/profile/render.py` | `llmtone prompt` |

### Evidence is the source of truth

`profile.json` is **derived**. It can be deleted and rebuilt from the evidence
log at any time, and rebuilding gives a byte-identical result.

That has three consequences worth stating plainly:

1. Determinism is a property of the design, not something the tests hope for.
2. Improving the scoring rules later re-scores everything you have already
   written — you never re-answer the questions.
3. `evidence → profile` is auditable. If a score surprises you, the input that
   produced it is still on disk.

---

## Dimensions

Eight, defined in `llmtone/scoring/dimensions.py`:

`formality` · `directness` · `warmth` · `conciseness` · `humour` · `hedging` ·
`technicality` · `conversationality`

Each produces a value of 0–100 and a confidence of 0–1.

### How a value is computed

Every dimension is a weighted sum of features. Nothing else. For example,
formality:

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

Each feature is mapped from its range in `FEATURE_RANGES` onto 0–100 and
clamped. A negative weight inverts the mapped value. The absolute weights sum
to 1.0 — asserted at import, so a bad edit fails loudly rather than producing a
quietly skewed profile.

`Dimension.contributions(features)` returns the per-feature breakdown, so you
can see exactly which feature moved a score.

### Ranges matter more than you'd think

`FEATURE_RANGES` maps each raw feature onto 0–100. If a range is much wider
than real writing ever reaches, that feature barely moves, and the dimension
quietly becomes a function of whichever feature *does* vary — usually sentence
length. The ranges shipped here were narrowed after checking them against the
test fixtures for exactly this reason.

If you tune anything, tune these first, and against your own writing.

---

## Confidence

Three factors, multiplied:

```
confidence = ceiling × coverage × consistency
```

**Ceiling** — can this be inferred reliably at all by counting words? A
per-dimension cap:

| Dimension | Ceiling | |
|---|---|---|
| formality, conciseness | 0.90 | strong, direct signals |
| technicality, conversationality | 0.88 | |
| directness, hedging | 0.85 | |
| warmth | 0.72 | partly tone, which words don't fully carry |
| humour | 0.55 | word counting cannot really detect humour |

Humour's ceiling is the honest part of the design. llmtone can see exclamation
marks and colloquialisms; it cannot see whether you are funny. The number says
so rather than pretending otherwise.

**Coverage** — `min(1.0, total_words / target_words)`. Target words differ per
dimension: conciseness shows up in 300 words, humour needs 900.

**Consistency** — how much the dimension varies across your samples:

```
consistency = max(0.30, 1 - stdev(per-sample values) / 50)
```

- Samples under 40 words are excluded — a six-word reply is noise, not
  disagreement.
- With one usable sample, consistency is a flat 0.70. There is nothing to be
  consistent *with*, and pretending to perfect agreement would be a lie.
- The 0.30 floor means conflicting evidence lowers confidence without erasing
  the observation. Contradictory samples usually mean you write differently in
  different contexts — which is a feature, not an error.

### Naming the contradiction

A lowered confidence says *something* disagreed. It does not say what. So the
same per-sample values that feed consistency are checked again, and a dimension
is reported as context-dependent when both of these hold:

| Test | Threshold | Why |
|---|---|---|
| range (`max - min`) | ≥ 30 points | about the distance between a work email and a message to a friend |
| scatter (stdev) | ≥ 15 points | a range is set by two extremes; scatter says the split is real |

Both, because range alone flags almost everything once you have a handful of
short samples — on a test corpus of seven it flagged seven of the eight
dimensions, which tells a reader nothing. The scatter test does *not* rule out a
single extreme sample, and shouldn’t: one formal email among five casual notes
is exactly the signal.

`llmtone profile` names the three widest and counts the rest; the full list is
in `notes.varies_by_context`, with the range so a consumer can see how far apart
the two habits are. See [schema.md](schema.md).

### Splitting instead of averaging

Naming the contradiction is half of it. The other half is doing something about
it: label a sample with where it was written and that context gets its own
profile.

```
llmtone analyse work-email.md --save --context work
llmtone prompt --context work
```

The label rides on the **evidence record**, not the profile, so contexts obey
the same rule as everything else here — the profile stays a function of the
log, and relabelling means appending evidence rather than editing a result.
Unlabelled writing belongs to no context: unlabelled means unknown, not
"other".

A context is scored by exactly the same function as the whole corpus, so its
confidence means the same thing. That has a consequence worth expecting rather
than being surprised by: **a context is usually more confident than the pooled
profile.** Two samples that contradict each other drag consistency down
together; split by where they were written, each side agrees with itself. This
is the payoff — a profile that was 0.30 confident about your formality because
you write two ways can be 0.63 confident about how you write at work.

A context needs 200 words before it appears at all. Below that every dimension
would score under the 0.45 threshold, so the entry would be a heading with
nothing under it.

What this does not do: it will not guess the labels. Clustering samples into
contexts nobody named would mean inventing a distance measure over style
vectors and then defending whatever it produced. A label you typed is worth
more than a cluster llmtone argued itself into.

### The threshold that matters

`render.py` treats **0.45** as the line between an observation and an
impression. Below it, a dimension is listed as "not yet confident" in the
summary and left out of the generated instructions entirely. Telling a model
"be quite funny" on 0.3 confidence is worse than saying nothing.

---

## Choosing what to ask next

`llmtone calibrate` picks questions instead of asking a fixed list. Three
numbers decide it, all in
[`llmtone/calibration/selection.py`](../llmtone/calibration/selection.py):

```
priority = uncertainty x importance / (1 + saturation)
```

**Uncertainty is measured against the ceiling, not against 1.0:**

```
uncertainty = (ceiling - confidence) / ceiling
```

On raw `1 - confidence`, humour would be the most uncertain dimension forever —
it caps at 0.55 — and every question would chase the one thing word-counting
cannot see. Measuring the gap to what is actually achievable means a dimension
drops out of the queue once it is as settled as it can get.

**Importance** (`calibration_importance` in `dimensions.py`) is how much getting
this dimension wrong would cost the reader: formality and directness 1.0,
humour 0.5. It affects nothing but question choice.

**Saturation** counts how many questions have already been aimed at a dimension,
weighting each question's targets by position — a question that touched warmth
third barely counts as having covered warmth. Selection re-ranks after every
pick, so a round of three spreads across three weak dimensions instead of asking
the same thing three ways.

Ties break on question id, so the same profile and history always produce the
same questions in the same order.

### What selection does not do

It chooses which question appears on the screen. That is all. The answer is
stored as evidence and analysed by the same code as any other sample — there is
no path by which "we asked about hedging" becomes "hedging is 60". Every
question's `targets` are written by hand in `questions.py`.

### Why confidence sometimes falls after calibrating

Because consistency is part of confidence. Answers that disagree with what was
already there lower it, which is the honest result: two samples that contradict
each other are less evidence for a single value than one sample was. The CLI
says so rather than hiding the drop.

---

## Vocabulary: prefer and avoid

`prefer` is evidence of **presence** — recurring *style* words and phrases you
actually used: hedges, colloquialisms, fillers, intensifiers, and repeated turns
of phrase. Reasonably trustworthy.

It deliberately excludes the most-repeated content words, which an earlier
version included. In a corpus of one person's writing, the most repeated words
are whatever they happen to write *about*, and a profile built from work emails
would tell a model to reach for "archive" and "reporting" — after which the
model dutifully writes about archives. Subject matter is reported separately as
`technical_terms`, where a consumer can treat it as domain vocabulary rather
than as voice.

`avoid` is evidence of **absence** — words from a curated candidate list
(`furthermore`, `leverage`, `utilize`, …) that never appear in your writing.
Much weaker, and treated accordingly:

- Nothing is claimed below 200 words, where absence means nothing.
- The strongest case is a formal word you never use whose plain equivalent you
  do (`utilize` absent, `use` present); that is preferred over bare absence.
- The profile carries `notes.avoid_inferred_from_absence: true`, and the CLI
  labels the list as a hint.

`llmtone calibrate` fixes this one word at a time. Shown "utilise" and "use"
and asked which you would write, your answer turns "you never wrote this" into
"you chose the other one" — evidence of preference rather than of silence.
Confirmed words sort to the top of `avoid` and are listed in
`notes.avoid_confirmed_by_choice`; the renderer tells a model to never use those
and to *probably* avoid the rest.

Which pairs get offered follows the same principle as everything else here:
first the words the profile has already guessed you avoid, because those are the
claims it is least entitled to make.

**A choice moves no dimension value and no confidence.** Saying you would write
"use" is not the same as being observed writing it, so a choice touches the
vocabulary lists and nothing else. The scorer stays a function of your writing
alone. Observed edits — the strongest evidence of all, because you did not know
you were being asked — are still to come.

---

## Changing the scoring

Everything you'd want to change is data:

| To change | Edit |
|---|---|
| what counts as a hedge/buzzword/colloquialism | `analysis/lexicons.py` |
| how much a feature matters | `weights` in `scoring/dimensions.py` |
| what counts as "a lot" of a feature | `FEATURE_RANGES` |
| how quickly confidence builds | `target_words`, `confidence_ceiling` |
| which dimension calibration chases | `calibration_importance` in `scoring/dimensions.py` |
| what calibration can ask | `CALIBRATION_QUESTIONS` in `calibration/questions.py` |
| how uncertainty is described | `scoring/scorer.py` constants |

The tests assert *relative* outcomes — the formal fixture scores higher on
formality than the casual one — rather than exact numbers, precisely so that
retuning is possible without rewriting the suite. If a change survives
`pytest`, it hasn't broken the ordering that matters.

The profile format is versioned and independent of all of this, so better
scoring later does not mean a new format.


---

## Where this comes from

llmtone is not a new idea, and the parts of it that are well founded are well
founded because someone else did the work.

**The design.** Douglas Biber’s multi-dimensional analysis is the direct
ancestor: co-occurring lexico-grammatical features reduced to a handful of
interpretable dimensions. His Dimension 1, *involved vs. informational
production*, loads contractions, second-person pronouns and private verbs on one
pole and nouns, long words and high type-token ratio on the other — the same
sign pattern as `conversationality` and `formality` here. The honest difference:
his loadings were derived by factor analysis over a corpus. Ours are hand-set,
and are a hypothesis about the same structure rather than a measurement of it.

**Contradiction detection.** Grieve et al., [*Register variation explains
stylometric authorship
analysis*](https://doi.org/10.1515/cllt-2022-0040) (CLLT 2023), argues that
stylometry works because authors write in subtly different registers rather than
different dialects. Within-author variation is therefore the expected case, not
a defect in the measurement — which is the whole justification for reporting a
spread instead of hiding it inside a lower confidence. The same literature finds
cross-register attribution collapsing towards chance, which is the argument that
per-context profiles are necessary rather than a nicety.

**Vocabulary diversity.** `vocabulary_diversity` is MTLD, from McCarthy &
Jarvis, [*MTLD, vocd-D, and HD-D*](https://doi.org/10.3758/BRM.42.2.381)
(Behavior Research Methods, 2010), which found it the only diversity index not
varying with text length. Later work on minimum lengths puts its usable floor
near 100 tokens, and `MIN_WORDS_FOR_CONSISTENCY` is 40 — so on a short sample
that feature is noisier than the rest, and it carries 0.15 of `technicality`.
Known, unfixed.

**Sample size.** Eder’s *Does size matter?* puts reliable authorship
*attribution* at 2,500–5,000 words. The `target_words` here are 300–900, so
`coverage: 1.0` should be read as “enough to describe how this person writes”,
never as “enough to identify them”. Different task, much lower bar.
