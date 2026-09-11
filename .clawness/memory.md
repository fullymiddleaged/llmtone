# Memory

## Lessons

- Bash tool mangles backslashes in heredocs (`\\n` arrives as a real newline) — write Python source via Write/Edit.
- New `.exe` console scripts are blocked on this box; test entry points with `python -c "from llmtone.cli import main"`.
- llmtone: LLM may extract evidence + wording; only dimension values/confidence stay deterministic. Not lexicon-limited.
- llmtone: cache LLM-derived evidence in evidence.jsonl so rescoring stays reproducible (profile = f(evidence log)).
- llmtone is public: .clawness/ session state is gitignored; only memory.md and rules/ are committed.
- llmtone: contradiction detection needs range>=30 AND stdev>=15 (scorer.py); range alone flagged 7 of 8 dimensions.
- This env mangles backslashes in Bash heredocs: build "\n" via chr(92) in patch scripts, or a real newline lands in the file.
- llmtone: storage.labelled_sample_texts() returns question answers too, not just samples; filter by label/kind.
