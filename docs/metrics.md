# Metrics

Everything llmtone measures, and how much to trust it.

All of it is computed by `llmtone/analysis/`, from plain regular expressions and
word lists. There is no model, no training and no randomness: the same text
produces the same numbers on every machine, forever.

Run `llmtone analyse --json FILE` to see all of this for a file of your own.

---

## Measurements

These are counts. They are exact, in the sense that they measure precisely what
they say they measure.

### Basic (`analysis/text.py`)

| Metric | Definition |
|---|---|
| `word_count` | Runs of letters/digits, joined by apostrophes or hyphens. `well-known` is one word; `it's` is one word. |
| `sentence_count` | See *Sentence splitting* below. |
| `paragraph_count` | Blocks separated by a blank line. |
| `average_sentence_length` | Words per sentence. |
| `sentence_length_variance` | Population variance of sentence lengths. High means you mix long and short; low means you don't. |
| `average_paragraph_length` | Words per paragraph. |
| `average_word_length` | Characters per word. |
| `long_word_rate` | Words of 7+ characters, per 100 words. |
| `vocabulary_diversity` | MTLD — see below. |

**Sentence splitting** breaks on `.`, `!` or `?` followed by whitespace, and
also at paragraph boundaries and between list items. The last two matter more
than they sound: headings and bullets are usually unpunctuated, and without
them a five-item bullet list registers as one enormous sentence and drags
`average_sentence_length` somewhere meaningless. Abbreviations (`Dr.`, `e.g.`,
`J. Smith`) are guarded against with a list in `text.py`.

**MTLD, not type-token ratio.** Raw TTR (unique words ÷ total words) falls
steadily as a text gets longer, so a 2000-word document always looks less
lexically varied than a 200-word email regardless of the writing. That makes it
useless for the one thing llmtone needs — comparing samples of different
lengths. MTLD measures how many words it takes, on average, for the running TTR
to fall below 0.72, which is stable across lengths. It returns 0.0 for texts
under 10 tokens, where the measure means nothing.

### Punctuation (`analysis/punctuation.py`)

Commas, periods, semicolons, colons, parentheses, em dashes, en dashes,
hyphens, exclamation marks, question marks, ellipses and quotes. Counts and
rates per 1000 words.

`--` counts as one em dash rather than two hyphens, and `...` as one ellipsis
rather than three periods.

**Bands are per mark.** 20 commas per 1000 words is unremarkable; 20 semicolons
per 1000 words is a personality. So `never`/`rare`/`occasional`/`frequent` is
computed against per-mark thresholds in `BAND_THRESHOLDS`, not one global scale.
Those thresholds are rough general-English base rates. They are a reasonable
starting point, not a finding — tune them if your corpus disagrees.

### Vocabulary (`analysis/vocabulary.py`)

Common, unusual and repeated words; technical terms; colloquialisms; fillers;
hedges; buzzwords; formal vocabulary.

Detection is by lookup in `analysis/lexicons.py`, plus shape-based rules for
technical vocabulary: `camelCase`, `snake_case`, `filename.ext`, `--flags`,
`` `code` ``, and 2–6 letter acronyms. The shape rules are what let llmtone spot
domain terminology it has never seen.

Phrases (`sort of`, `circle back`, `catching fire`) are counted separately from
single words, so `kind regards` is not scored as hedging the way `kind of` is.

---

## Approximations

Three metrics are heuristics standing in for something that properly needs a
parser. They are flagged as `approximate` in every output that carries them, and
`notes.approximate_metrics` in the profile lists them. Here is exactly how each
one is wrong.

### Passive voice

A be-verb (optionally plus an adverb) followed by a past participle, with a
short list of common irregulars.

- **False positives** on adjectival participles: *"the team is interested in
  this"*, *"we are excited"*, *"it is complicated"*.
- **False negatives** on irregular participles outside the list, and on
  reduced passives: *"the report, written last week, ..."*.
- Reported per 100 sentences, so a document of very long sentences will look
  less passive than one of short sentences at the same density.

Treat it as "this writing leans passive" rather than as a passive count.

### Sentence fragments

A sentence containing no word from a finite-verb list and no verb-shaped token
(a word of 3+ characters ending `-ed`, `-ing`, `-es` or `-s`).

- **Undercounts badly.** Any fragment built around an ordinary verb is missed.
- **Verb-shaped is not verb**: *"Various process changes."* has no verb but
  `changes` looks like one, so it is not flagged.
- Imperative fragments (*"Bin it."*) are caught only when the verb is outside
  the cue list.

The absolute number is not meaningful. Its movement between two texts by the
same person roughly is.

### Subordinate clauses

A count of subordinating keywords (`although`, `because`, `while`, `which`, …).

- It counts *words*, not clauses. One sentence with three subordinators counts
  three.
- `that` and `as` are excluded because they are far more often not
  subordinators, which means genuine subordinate clauses using them are missed.

It is a proxy for syntactic complexity. It is not a parse and does not pretend
to be one.

---

## Rates, and why they are what they are

Word-level features are per 100 words. Sentence-level features (passive,
questions, fragments, imperatives, subordinators) are per 100 sentences.
Punctuation is per 1000 words.

The normalisation is the point: it is what lets a 20-word Slack message and a
2000-word document be compared at all. When several samples are combined into a
profile they are analysed as one concatenated corpus, so counts stay exact and a
long document naturally carries more weight than a short one — no averaging of
averages, and no weighting arithmetic to get wrong.

---

## What is deliberately not measured

- **Sentiment.** Not a writing habit.
- **Readability scores** (Flesch, etc.). They are functions of sentence and word
  length, which are already reported directly and more usefully.
- **Anything requiring a parser or a model.** Phase 1 is stdlib-only on purpose;
  a dependency has to materially improve a metric to earn its place.
