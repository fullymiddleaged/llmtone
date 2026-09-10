# Privacy

## What leaves your machine

Nothing.

Not "nothing by default" — nothing. llmtone 0.1 contains no network code at
all. There is no HTTP client, no socket, no telemetry, no update check, and no
optional flag that would enable one. You can check:

```bash
# Every module llmtone imports. All stdlib, none of them networking.
grep -rhE "^(import|from) " llmtone/ --include="*.py" | sort -u
```

`tests/test_privacy.py` asserts the same thing, so it stays true.

The only dependency is Python itself. The package declares zero runtime
dependencies, so there is no third-party code in the install that could phone
home either.

This will stop being true when optional LLM providers arrive in Phase 4. When
they do, this document will say exactly what is sent, to whom, and what has to
be configured for it to happen. Until then the guarantee is structural rather
than a promise about behaviour, which is the strongest kind available.

## What is stored, and where

```
~/.llmtone/
├── profile.json      your derived profile
├── evidence.jsonl    one record per answer or sample
└── samples/          your writing, exactly as you gave it
```

Override the location with `LLMTONE_HOME`.

All of it is plain text. Read it, diff it, edit it, delete it, put it in a
private git repo — it is yours, and there is no format between you and it.

- **`samples/`** holds your writing verbatim. It is kept because a future
  scoring improvement needs to re-analyse the original text rather than ask you
  to write it again. Delete a sample file and rerun `llmtone init --force`, or
  just delete the whole directory, and it is gone.
- **`evidence.jsonl`** holds metrics and references, never raw text. The
  filename in `text_ref` points into `samples/`. Any context label you pass to
  `--context` is stored here too, and copied into `profile.json` as a key under
  `contexts` — so pick labels you would not mind a consumer of the profile
  seeing, or leave the sample unlabelled.
- **`profile.json`** holds scores, bands and short word lists. Ordinary
  subject-matter words do not reach it — the vocabulary lists are style words
  (hedges, colloquialisms, fillers) plus a curated avoid list. Two things
  drawn from your writing do: `technical_terms`, which is shape-detected and
  will happily pick up an internal service name or a filename, and
  `phrasing.preferred`, which holds short recurring turns of phrase.

Files are written with `0600` permissions where the platform supports it, and
written atomically (temp file, then rename) so an interrupted write cannot
corrupt a profile.

## What is not done

- **No account.** There is nothing to sign up for.
- **No database.** Files only.
- **No logging of your writing.** Errors print the error, never the text that
  caused it.
- **No prose is retained outside `samples/`.** Metrics, the evidence log and
  the profile hold no sentences — a test asserts that no three-word run from a
  source sentence survives into the metric dump. They *do* hold individual
  words, because a vocabulary profile is made of words; see the note on sharing
  below.
- **No API keys in the profile.** There are no API keys in Phase 1 at all; when
  providers arrive they will read from the environment, and the profile file
  will remain something you can share without leaking a credential.

## Sharing a profile

`llmtone export` prints `profile.json`. It contains no credentials and no
prose — but before handing it to anyone, skim two fields:

- **`vocabulary.technical_terms`** — detected by shape (`camelCase`,
  `snake_case`, `filename.ext`, acronyms), so it picks up internal service
  names and file paths along with genuine domain vocabulary.
- **`phrasing.preferred`** — short phrases you repeat.

Both are a handful of entries, and you can delete anything you'd rather not
share. Everything else in the file is scores and bands.

## The schema is public on purpose

`voice-profile.schema.json` is published so any tool can read or write this
format without depending on llmtone. The goal is a portable format you own, not
a file only one program understands.
