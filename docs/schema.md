# The voice profile format

The canonical definition is [`voice-profile.schema.json`](../voice-profile.schema.json)
— real JSON Schema (draft 2020-12), published so that any tool can read or write
this format without depending on llmtone.

That is the point of the format existing at all: a portable description of how
someone writes, which they own, and which no single tool controls.

## Reading a profile

```json
{
  "version": "1.0",
  "profile_id": "8f2c1a9e4b7d0356",

  "style": {
    "formality":         { "value": 20, "confidence": 0.69 },
    "directness":        { "value": 59, "confidence": 0.58 },
    "conversationality": { "value": 63, "confidence": 0.74 }
  },

  "syntax": {
    "average_sentence_length": 9.7,
    "sentence_length_variance": 41.2,
    "contraction_preference": 0.79,
    "fragment_preference": 0.14
  },

  "punctuation": {
    "semicolon": "never",
    "em_dash": "never",
    "comma": "occasional"
  },

  "vocabulary": {
    "prefer": ["definitely", "rather"],
    "avoid": ["leverage", "furthermore"],
    "technical_terms": ["logs", "deployment", "pipeline"],
    "colloquialisms": ["bin", "fall over"]
  },

  "phrasing": { "preferred": ["i'd probably"], "avoided": [] },
  "structure": { "paragraph_length": "short", "bullet_preference": "medium" },
  "contexts": {},
  "metadata": { "sample_count": 6, "word_count": 473 },
  "notes": { "avoid_inferred_from_absence": true, "avoid_confirmed_by_choice": ["thus", "hence"] }
}
```

## Field guide

### `style` — required

Dimension name to `{value, confidence}`.

- `value` is an integer 0–100.
- `confidence` is 0–1. **Treat anything below 0.45 as not established** and
  ignore it rather than acting on it.

llmtone currently emits eight dimensions. A consumer should **ignore dimensions
it does not recognise** rather than fail — that is how the format grows without
breaking anything.

### `syntax`

Observed habits, all optional.

`contraction_preference` and `fragment_preference` are 0–1 ratios, not rates.
Contraction preference answers "when you *could* contract, how often do you?",
which is a style signal; a raw contraction rate mostly tracks how often you use
pronouns.

### `punctuation`

Mark to one of `never` · `rare` · `occasional` · `frequent`.

Bands are relative to typical usage **of that mark**, not to each other. `comma:
rare` and `semicolon: rare` describe very different absolute frequencies. See
[metrics.md](metrics.md).

### `vocabulary`

| Field | What it is | Trust |
|---|---|---|
| `prefer` | style words and phrases they use | good |
| `avoid` | words absent from their writing | weak — see below |
| `technical_terms` | domain vocabulary, detected by lexicon and by shape | good |
| `colloquialisms` | informal vocabulary they use | good |

`avoid` mixes two kinds of evidence, and the notes tell them apart. Entries in
`notes.avoid_confirmed_by_choice` were chosen against directly — the person was
shown "utilise" and "use" and picked one (`llmtone calibrate`) — so they can be
enforced strictly. The rest are inferred from **absence**, which is much weaker,
and `notes.avoid_inferred_from_absence` stays true while any remain. Confirmed
entries sort first. The absence-based part is empty below 200 words of
evidence.

`prefer` is style vocabulary only. Subject matter lives in `technical_terms`, so
a consumer can use one for voice and the other for domain without confusing the
two.

### `structure`

`paragraph_length`: `short` · `medium` · `long`.
`heading_preference` and `bullet_preference`: `low` · `medium` · `high`.

### `contexts`

Per-context overrides — `work`, `casual`, `public`, `technical`, or a custom
name — each a partial profile of the same shape, overriding the top level.

**Always `{}` in Phase 1.** Contexts only appear once there is evidence that
someone genuinely writes differently in different settings; inventing them up
front would mean asking five questions to fill in boxes nobody asked for.

### `metadata`

`sample_count` and `word_count` are required — they are how a consumer judges
how much writing the profile rests on. Timestamps and generator are optional.

### `notes`

Caveats about how the numbers were produced: which metrics are approximations,
whether `avoid` came from absence, and a plain statement that the profile
describes writing behaviour rather than personality.

Nothing here is machine-critical, and everything here is the difference between
a number and an honest number.

## Versioning

`version` is `MAJOR.MINOR`.

- **Minor** bumps add fields or dimensions. Keep reading; ignore what you don't
  know.
- **Major** bumps change meaning. Refuse a major version you don't understand
  rather than guessing.

The format is deliberately independent of llmtone's scoring rules, which are
expected to improve. Better scoring does not mean a new format.

## Writing a profile from another tool

Emit `version`, `profile_id`, `style` and `metadata` and you have a valid
profile. Everything else is optional. If you cannot estimate a confidence
honestly, leave the dimension out — an absent dimension is far more useful than
a confident-looking guess.
