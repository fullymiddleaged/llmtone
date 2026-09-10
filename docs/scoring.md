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
  different contexts — which is a Phase 2 feature, not an error.

### The threshold that matters

`render.py` treats **0.45** as the line between an observation and an
impression. Below it, a dimension is listed as "not yet confident" in the
summary and left out of the generated instructions entirely. Telling a model
"be quite funny" on 0.3 confidence is worse than saying nothing.

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

This is the weakest part of Phase 1 and the clearest argument for Phase 2.
Calibration answers and, later, observed edits turn "you never wrote this" into
"you chose the other one" — evidence of preference rather than evidence of
silence.

---

## Changing the scoring

Everything you'd want to change is data:

| To change | Edit |
|---|---|
| what counts as a hedge/buzzword/colloquialism | `analysis/lexicons.py` |
| how much a feature matters | `weights` in `scoring/dimensions.py` |
| what counts as "a lot" of a feature | `FEATURE_RANGES` |
| how quickly confidence builds | `target_words`, `confidence_ceiling` |
| how uncertainty is described | `scoring/scorer.py` constants |

The tests assert *relative* outcomes — the formal fixture scores higher on
formality than the casual one — rather than exact numbers, precisely so that
retuning is possible without rewriting the suite. If a change survives
`pytest`, it hasn't broken the ordering that matters.

The profile format is versioned and independent of all of this, so better
scoring later does not mean a new format.
