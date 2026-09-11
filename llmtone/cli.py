"""The llmtone command line.

    llmtone init          five questions, then a writing sample per tone
    llmtone analyse FILE  metrics for one file (--save --context work)
    llmtone profile       your profile, as bars and prose
    llmtone prompt        model-independent writing instructions (--context)
    llmtone export        the profile as JSON
    llmtone calibrate     more questions, chosen by what is least certain
    llmtone check FILE    (Phase 3)

Colour is written by hand rather than pulled in as a dependency, and turns
itself off when output is not a terminal or NO_COLOR is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from . import __version__
from .analysis import analyse
from .calibration import (
    ONBOARDING_QUESTIONS,
    answered_pair_ids,
    answered_question_ids,
    record_calibration,
    record_choice,
    record_response,
    record_sample,
    select_pairs,
    select_questions,
    verdicts_from_evidence,
)
from .calibration.pairs import SKIP
from .calibration.questions import MIN_ANSWER_WORDS
from .calibration.selection import DEFAULT_ROUND, dimension_priority
from .evidence import utc_now
from .integrate import (
    DEFAULT_TARGET,
    BlockError,
    refresh_command,
    render_block,
    write_block,
)
from .profile import (
    CONFIDENCE_THRESHOLD,
    MIN_CONTEXT_WORDS,
    PRESET_CONTEXTS,
    Storage,
    normalise_context,
    build_profile,
    render_instructions,
    render_summary,
)
from .scoring import DIMENSIONS

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_YET = 2

_NOT_YET_MESSAGE = (
    "`llmtone {name}` lands in Phase 3. Today: init, calibrate, analyse, "
    "profile, prompt and export."
)

#: Confidence moves smaller than this are rounding, not progress.
CONFIDENCE_DELTA_FLOOR = 0.01

#: A context has to sit this far from your overall value before it is worth a
#: line. Closer than this and it is the same voice with a different subject.
CONTEXT_DELTA_SHOWN = 10

#: Dimensions listed by name when the samples disagree. The rest are counted,
#: because a list naming most of the eight says nothing.
VARIATION_SHOWN = 3

#: Word choices offered per calibration round. Quick to answer, so a couple
#: alongside the written questions costs nothing.
DEFAULT_PAIRS = 2


# --- output helpers ---------------------------------------------------------
def _colour_enabled(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("LLMTONE_FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def _supports(stream, text: str) -> bool:
    """Can this stream actually encode ``text``?

    Windows consoles still default to cp1252, which cannot represent the block
    characters used for the bars. Asking first is cheaper than crashing on the
    first line of output.
    """
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return True
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


class Out:
    """Minimal ANSI writer. Nothing here needs a library."""

    #: (filled, empty) bar characters, preferred first.
    BLOCKS = ("█", "░")
    ASCII_BLOCKS = ("#", ".")

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout
        self.colour = _colour_enabled(self.stream)
        self.blocks = (
            self.BLOCKS if _supports(self.stream, "".join(self.BLOCKS))
            else self.ASCII_BLOCKS
        )

    def _wrap(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.colour else text

    def bold(self, text: str) -> str:
        return self._wrap(text, "1")

    def dim(self, text: str) -> str:
        return self._wrap(text, "2")

    def cyan(self, text: str) -> str:
        return self._wrap(text, "36")

    def yellow(self, text: str) -> str:
        return self._wrap(text, "33")

    def say(self, text: str = "") -> None:
        print(text, file=self.stream)

    def bar(self, value: int, width: int = 10) -> str:
        return bar(value, width, self.blocks)


def bar(value: int, width: int = 10, blocks: tuple[str, str] = ("█", "░")) -> str:
    """A 0-100 value as a filled/empty block bar."""
    filled = int(round(max(0, min(100, value)) / 100 * width))
    return blocks[0] * filled + blocks[1] * (width - filled)


def confidence_marker(confidence: float) -> str:
    if confidence >= 0.7:
        return "  "
    if confidence >= 0.45:
        return " ?"
    return " ??"


# --- commands ---------------------------------------------------------------
def _rebuild(storage: Storage, out: Out) -> None:
    """Rebuild profile.json from the evidence log."""
    labelled = storage.labelled_sample_texts()
    existing = storage.load_profile()
    profile = build_profile(
        [text for text, _ in labelled],
        labels=[label for _, label in labelled],
        verdicts=verdicts_from_evidence(storage.evidence()),
        profile_id=existing.profile_id if existing else uuid.uuid4().hex[:16],
        created_at=(
            existing.metadata.get("created_at") if existing else None
        ) or utc_now(),
        updated_at=utc_now(),
    )
    path = storage.save_profile(profile)
    out.say(out.dim(f"Profile written to {path}"))


def _read_answers_file(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("answers file must be a JSON object of id -> answer")
    return {str(k): str(v) for k, v in data.items()}


def _prompt_multiline(out: Out, label: str) -> str:
    """Read a possibly multi-line answer, ending at a blank line or EOF."""
    out.say(out.dim(label))
    lines: list[str] = []
    while True:
        try:
            line = input()
        except (EOFError, OSError):
            break
        if not line.strip() and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip()


#: Ends a pasted writing sample. A blank line cannot: real writing has
#: paragraphs in it, and a paste that stopped at the first one would never
#: reach the words a context needs.
PASTE_END = "."


def _prompt_paste(out: Out, label: str) -> str:
    """Read a writing sample, ending at a line holding a single full stop."""
    out.say(out.dim(label))
    lines: list[str] = []
    while True:
        try:
            line = input()
        except (EOFError, OSError):
            break
        if line.strip() == PASTE_END:
            break
        lines.append(line)
    return "\n".join(lines).strip()


#: How each preset tone is asked for. An unknown label falls back to the
#: generic ask, so a context nobody anticipated can still onboard itself.
_CONTEXT_HINTS = {
    "business": "Work writing -- an email to a colleague or a client, a status "
                "update, a ticket.",
    "friendly": "Friendly writing -- a message to a friend, a chat thread, "
                "something social.",
    "marketing": "Marketing writing -- a launch post, a product page, an "
                 "announcement.",
    "code": "Code comments -- docstrings, a pull request description, a code "
            "review.",
}

_PASTE_LABEL = (
    "  Paste it below, then a line with a single . to finish. "
    "Just . on its own skips this one."
)


def _context_hint(name: str) -> str:
    return _CONTEXT_HINTS.get(name, f"Something you wrote in the {name!r} setting.")


def _add_context_hint(name: str) -> str:
    return f"  Build one with: llmtone analyse FILE --save --context {name}"


def _split_sample_arg(value: str) -> tuple[Path, str | None]:
    """Split ``--sample FILE:CONTEXT``, leaving a Windows drive letter alone.

    ``C:\\writing\\work.txt`` is a path, not a file called ``C`` in a context
    called ``\\writing\\work.txt``, so a separator in the tail means there was
    no label.
    """
    head, separator, tail = value.rpartition(":")
    if not separator or not head or not tail:
        return Path(value), None
    if any(mark in tail for mark in ("/", os.sep)):
        return Path(value), None
    return Path(head), tail


def _context_words(storage: Storage, context: str) -> int:
    """Words stored against one context, across every sample so far."""
    return sum(
        len(text.split())
        for text, label in storage.labelled_sample_texts()
        if label == context
    )


def _store_sample(
    storage: Storage,
    out: Out,
    text: str,
    *,
    source: str,
    context: str | None,
    seq: int,
) -> None:
    """Record one sample and say whether its context has enough writing yet.

    Below ``MIN_CONTEXT_WORDS`` a context is stored but does not appear in the
    profile. Saying nothing would make a paste look like it vanished, so the
    shortfall is always named.
    """
    record_sample(storage, text, source=source, seq=seq, context=context)
    words = len(text.split())
    if context is None:
        out.say(out.dim(f"  noted ({words} words)"))
        return
    name = normalise_context(context)
    total = _context_words(storage, name)
    if total >= MIN_CONTEXT_WORDS:
        out.say(out.dim(f"  noted ({words} words) -- enough for a {name!r} profile"))
        return
    out.say(out.dim(
        f"  noted ({words} words) -- {MIN_CONTEXT_WORDS - total} more before "
        f"{name!r} gets its own profile"
    ))
    out.say(out.dim(f"  add to it later: llmtone analyse FILE --save --context {name}"))


def _record_sample_files(
    storage: Storage,
    out: Out,
    samples: list[tuple[Path, str | None]],
    seq: int,
) -> int:
    """Record every ``--sample`` given on the command line."""
    recorded = 0
    for path, context in samples:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            out.say(out.dim(f"  {path} is empty -- skipped"))
            continue
        label = f" as {normalise_context(context)}" if context else ""
        out.say(out.dim(f"  read {len(text.split())} words from {path}{label}"))
        _store_sample(
            storage, out, text, source=str(path), context=context, seq=seq + recorded
        )
        recorded += 1
    return recorded


def _collect_preset_samples(storage: Storage, out: Out, seq: int) -> int:
    """Ask for one paste per preset tone. Every one of them is skippable."""
    recorded = 0
    for name in PRESET_CONTEXTS:
        out.say(out.cyan(_context_hint(name)))
        text = _prompt_paste(out, _PASTE_LABEL)
        if not text.strip():
            out.say(out.dim("  skipped"))
            out.say()
            continue
        _store_sample(
            storage, out, text, source="pasted", context=name, seq=seq + recorded
        )
        recorded += 1
        out.say()
    return recorded


def cmd_init(args: argparse.Namespace, out: Out) -> int:
    storage = Storage.open(args.home)

    if storage.profile_exists() and not args.force:
        out.say(
            f"A profile already exists at {storage.profile_path}.\n"
            "Use --force to start over, or `llmtone analyse --save FILE` to "
            "add another sample to it."
        )
        return EXIT_ERROR

    scripted = _read_answers_file(Path(args.answers)) if args.answers else None

    samples = [_split_sample_arg(value) for value in (args.sample or [])]
    missing = [str(path) for path, _ in samples if not path.exists()]
    if missing:
        out.say("No such file: " + ", ".join(missing))
        return EXIT_ERROR

    out.say(out.bold("llmtone init"))
    out.say(
        "Five questions, then a few things you've actually written.\n"
        "Everything stays on this machine -- llmtone has no network code at "
        "all in this version.\n"
    )

    seq = 0
    answered = 0
    for question in ONBOARDING_QUESTIONS:
        out.say(out.cyan(question.text))
        if scripted is not None:
            answer = scripted.get(question.id, "")
            if answer:
                out.say(out.dim(f"  (from {args.answers})"))
        else:
            answer = _prompt_multiline(out, f"  {question.hint} (blank line to finish)")
        if not answer.strip():
            out.say(out.dim("  skipped"))
            out.say()
            continue
        words = len(answer.split())
        if words < MIN_ANSWER_WORDS:
            out.say(out.dim(f"  noted ({words} words -- a bit short, but fine)"))
        record_response(storage, question, answer, seq)
        seq += 1
        answered += 1
        out.say()

    out.say(out.bold("Now things you've actually written -- one per tone."))
    out.say(
        "Skip any tone you don't write in: llmtone only reports writing it has "
        "seen, so a tone with no samples gets no profile.\n"
        + out.yellow("Don't rewrite anything first. We want to see how you actually write.")
        + "\n"
        + out.dim(
            f"  About {MIN_CONTEXT_WORDS} words a tone -- two or three emails, a "
            "handful of messages -- before that tone gets its own profile. "
            "Anything shorter still counts towards your overall voice."
        )
        + "\n"
    )

    recorded = (
        _record_sample_files(storage, out, samples, seq)
        if samples
        else _collect_preset_samples(storage, out, seq)
    )

    if not recorded and answered == 0:
        out.say("Nothing to analyse. Run `llmtone init` again when you have a moment.")
        return EXIT_ERROR

    out.say()
    _rebuild(storage, out)
    profile = storage.load_profile()
    if profile:
        out.say()
        _print_profile(profile, out)
    return EXIT_OK


def cmd_analyse(args: argparse.Namespace, out: Out) -> int:
    path = Path(args.file)
    if not path.exists():
        out.say(f"No such file: {path}")
        return EXIT_ERROR
    text = path.read_text(encoding="utf-8")
    analysis = analyse(text)

    if args.json:
        out.say(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False))
    else:
        basic = analysis.basic
        out.say(out.bold(f"Analysis of {path.name}"))
        out.say()
        out.say(f"  Words                    {basic.word_count:,}")
        out.say(f"  Sentences                {basic.sentence_count:,}")
        out.say(f"  Paragraphs               {basic.paragraph_count:,}")
        out.say(f"  Avg sentence length      {basic.average_sentence_length}")
        out.say(f"  Sentence length variance {basic.sentence_length_variance}")
        out.say(f"  Avg paragraph length     {basic.average_paragraph_length}")
        out.say(f"  Vocabulary diversity     {basic.vocabulary_diversity} (MTLD)")
        out.say()
        out.say(out.bold("  Scored in isolation"))
        for dimension in DIMENSIONS:
            value = int(round(dimension.score(analysis.features)))
            out.say(f"    {dimension.name:<18} {value:>3}  {out.bar(value)}")
        out.say()
        out.say(
            out.dim(
                "  passive voice, fragments and subordinate clauses are "
                "approximations -- see docs/metrics.md"
            )
        )

    if args.save:
        storage = Storage.open(args.home)
        out.say()
        _store_sample(
            storage,
            out,
            text,
            source=str(path),
            context=args.context,
            seq=len(storage.evidence()),
        )
        _rebuild(storage, out)
    return EXIT_OK


def _print_variation(profile, out: Out) -> None:
    """Name the dimensions the samples disagree about.

    Confidence already went down for these -- consistency is a factor in it --
    but a lowered number does not tell anyone *what* disagreed. A spread this
    wide almost always means the samples came from different settings, so say
    that rather than leaving it looking like a fault.
    """
    varies = profile.notes.get("varies_by_context") or []
    if not varies:
        return
    out.say()
    out.say(out.bold("  You write very differently in different places"))
    for entry in varies[:VARIATION_SHOWN]:
        name = str(entry.get("dimension", "")).capitalize()
        out.say(
            f"    {name:<18} {entry['low']}-{entry['high']} across samples"
        )
    rest = len(varies) - VARIATION_SHOWN
    if rest > 0:
        others = ", ".join(
            str(e.get("dimension", "")) for e in varies[VARIATION_SHOWN:]
        )
        out.say(out.dim(f"    and {rest} more: {others}"))
    out.say(
        out.dim(
            "  That is context, not error -- but the single value above is an "
            "average of both."
        )
    )
    if not profile.contexts:
        out.say(
            out.dim(
                "  Split them with: llmtone analyse FILE --save --context work"
            )
        )


def _print_contexts(profile, out: Out) -> None:
    """Show each context as its distance from the overall profile.

    Not another eight bars per context: the useful thing is what *shifts*. A
    shift is only shown where the context is confident enough to claim it, so a
    thin context says it is thin rather than reporting a swing built on two
    paragraphs.
    """
    if not profile.contexts:
        return
    out.say()
    out.say(out.bold("  How that shifts by context"))
    for name in sorted(profile.contexts):
        entry = profile.contexts[name]
        meta = entry.get("metadata", {})
        count = meta.get("sample_count", 0)
        out.say(
            f"    {name}  "
            + out.dim(
                f"({count} sample{'' if count == 1 else 's'}, "
                f"{meta.get('word_count', 0):,} words)"
            )
        )
        shifts = []
        for dimension, score in (entry.get("style") or {}).items():
            overall = profile.style.get(dimension)
            if overall is None or score["confidence"] < CONFIDENCE_THRESHOLD:
                continue
            delta = score["value"] - overall.value
            if abs(delta) >= CONTEXT_DELTA_SHOWN:
                shifts.append((dimension, score["value"], delta))
        shifts.sort(key=lambda item: (-abs(item[2]), item[0]))
        if not shifts:
            out.say(out.dim("      much like your overall voice, so far"))
            continue
        for dimension, value, delta in shifts[:VARIATION_SHOWN]:
            out.say(
                f"      {dimension.capitalize():<18} {value:>3}  "
                + out.dim(f"{delta:+d} vs overall")
            )
        rest = len(shifts) - VARIATION_SHOWN
        if rest > 0:
            out.say(out.dim(f"      and {rest} more"))
    out.say(out.dim("  Write for one of these with: llmtone prompt --context NAME"))


def _print_profile(profile, out: Out) -> None:
    out.say(out.bold("Your Voice Profile"))
    out.say()
    uncertain = False
    for dimension in DIMENSIONS:
        score = profile.style.get(dimension.name)
        if score is None:
            continue
        marker = confidence_marker(score.confidence)
        uncertain = uncertain or marker.strip() != ""
        out.say(
            f"  {dimension.name.capitalize():<18} {score.value:>3}  "
            f"{out.bar(score.value)}  {out.dim(f'conf {score.confidence:.2f}')}{marker}"
        )
    out.say()
    metadata = profile.metadata
    out.say(f"  Samples analysed: {metadata.get('sample_count', 0)}")
    out.say(f"  Words analysed:   {metadata.get('word_count', 0):,}")
    if uncertain:
        out.say()
        out.say(out.dim("  ? low confidence   ?? not yet established"))
    _print_variation(profile, out)
    _print_contexts(profile, out)
    out.say()
    out.say(render_summary(profile))


def _require_profile(args: argparse.Namespace, out: Out):
    storage = Storage.open(args.home)
    profile = storage.load_profile()
    if profile is None:
        out.say(
            f"No profile at {storage.profile_path}. Run `llmtone init` first."
        )
        return None
    return profile


def cmd_profile(args: argparse.Namespace, out: Out) -> int:
    profile = _require_profile(args, out)
    if profile is None:
        return EXIT_ERROR
    _print_profile(profile, out)
    return EXIT_OK


def _start_context(args: argparse.Namespace, out: Out, name: str, known):
    """Report a context that has no writing behind it, then offer to start it.

    Asking for a paste here is how a person ends up with a collection of
    profiles: they meet a missing context at the moment they wanted it, rather
    than having to plan their tones out during onboarding. Returns the rebuilt
    profile, or ``None`` if the context still does not exist.
    """
    listed = ", ".join(sorted(known)) or "none yet"
    out.say(f"No profile for context {name!r}. Known contexts: {listed}.")
    hint = out.dim(_add_context_hint(name))
    if not sys.stdin.isatty():
        out.say(hint)
        return None

    out.say()
    out.say(out.bold("Start one now?"))
    out.say(out.cyan(_context_hint(name)))
    text = _prompt_paste(out, _PASTE_LABEL)
    if not text.strip():
        out.say(hint)
        return None

    storage = Storage.open(args.home)
    _store_sample(
        storage, out, text, source="pasted", context=name,
        seq=len(storage.evidence()),
    )
    out.say()
    _rebuild(storage, out)
    profile = storage.load_profile()
    if profile is None or name not in profile.contexts:
        out.say()
        out.say(f"Saved -- but that is not enough {name!r} writing for its own profile yet.")
        return None
    out.say()
    return profile


def cmd_prompt(args: argparse.Namespace, out: Out) -> int:
    profile = _require_profile(args, out)
    if profile is None:
        return EXIT_ERROR
    wanted = getattr(args, "context", None)
    name = None
    if wanted:
        name = normalise_context(wanted)
        if name not in profile.contexts:
            profile = _start_context(args, out, name, profile.contexts)
            if profile is None:
                return EXIT_ERROR
        profile = profile.for_context(name)
    instructions = render_instructions(profile)

    target = getattr(args, "write", None)
    if target:
        block = render_block(instructions, context=name, target=target)
        try:
            action = write_block(Path(target), block)
        except BlockError as exc:
            out.say(f"Left {target} alone: {exc}")
            return EXIT_ERROR
        said = {
            "created": "created it",
            "appended": "added the llmtone block",
            "replaced": "replaced the llmtone block",
        }[action]
        out.say(f"Wrote {target} -- {said}.")
        out.say(out.dim(f"Rerun {refresh_command(target, name)} after more writing."))
        return EXIT_OK

    if wanted:
        out.say(out.dim(f"# How you write in: {name}"))
    out.say(instructions)
    return EXIT_OK


def cmd_export(args: argparse.Namespace, out: Out) -> int:
    profile = _require_profile(args, out)
    if profile is None:
        return EXIT_ERROR
    payload = profile.to_json()
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
        out.say(out.dim(f"Written to {args.output}"))
    else:
        out.say(payload)
    return EXIT_OK


def _confidences(profile) -> dict[str, float]:
    return {name: score.confidence for name, score in profile.style.items()}


def _report_movement(out: Out, before: dict[str, float], after: dict[str, float]) -> None:
    """Show what the answers actually bought, in confidence terms."""
    moved = [
        (name, before.get(name, 0.0), after[name])
        for name in after
        if abs(after[name] - before.get(name, 0.0)) >= CONFIDENCE_DELTA_FLOOR
    ]
    if not moved:
        out.say(out.dim("  No dimension moved much. More writing is what shifts these."))
        return
    out.say(out.bold("What that changed"))
    out.say()
    for name, old, new in moved:
        out.say(
            f"  {name.capitalize():<18} conf {old:.2f} -> {new:.2f}  "
            + out.dim("up" if new > old else "down")
        )
    if any(new < old for _, old, new in moved):
        out.say()
        out.say(
            out.dim(
                "  Some fell. More evidence that disagrees with the evidence "
                "already there lowers confidence -- that is the consistency "
                "term doing its job, not a fault. See docs/scoring.md."
            )
        )


def _prompt_choice(out: Out, pair) -> tuple[bool, str | None]:
    """Ask one A/B word choice. Returns (answered, chosen-word-or-None)."""
    out.say(out.cyan(pair.question()))
    out.say(f"  1) {pair.formal}")
    out.say(f"  2) {pair.plain}")
    while True:
        out.say(out.dim("  [1, 2, n for neither, Enter to skip]"))
        try:
            reply = input().strip().lower()
        except (EOFError, OSError):
            # No one is there to answer -- a pipe, or a closed stdin.
            return (False, None)
        if reply == "":
            return (False, None)
        if reply in ("1", pair.formal):
            return (True, pair.formal)
        if reply in ("2", pair.plain):
            return (True, pair.plain)
        if reply in ("n", SKIP):
            return (True, None)
        out.say(out.dim("  Sorry -- 1, 2, n, or Enter."))


def _scripted_choice(pair, scripted: dict[str, str]) -> tuple[bool, str | None]:
    """Resolve one choice from a --choices file. A missing key means skip."""
    if pair.id not in scripted:
        return (False, None)
    value = str(scripted[pair.id]).strip().lower()
    if value in (pair.formal, pair.plain):
        return (True, value)
    if value in (SKIP, "n", "none"):
        return (True, None)
    raise ValueError(
        f"{pair.id}: expected {pair.formal!r}, {pair.plain!r} or {SKIP!r}, "
        f"got {value!r}"
    )


def _run_pairs(storage: Storage, out: Out, pairs, scripted, seq: int) -> int:
    """Offer the word choices. Returns how many were answered."""
    if not pairs:
        return 0
    out.say(out.bold("Two ways of saying the same thing."))
    out.say(
        out.dim(
            "Your avoid list is otherwise guesswork -- words you happen not to "
            "have written yet. Picking one of these makes it evidence."
        )
    )
    out.say()
    answered = 0
    for pair in pairs:
        if scripted is not None:
            found, chosen = _scripted_choice(pair, scripted)
            if found:
                out.say(out.cyan(f"{pair.formal} / {pair.plain}"))
                out.say(out.dim(f"  chose: {chosen or SKIP}"))
        else:
            found, chosen = _prompt_choice(out, pair)
        if not found:
            out.say(out.dim(f"  {pair.formal} / {pair.plain}: skipped"))
            out.say()
            continue
        record_choice(storage, pair, chosen, seq + answered)
        answered += 1
        out.say()
    return answered


def cmd_calibrate(args: argparse.Namespace, out: Out) -> int:
    """Ask about whatever the profile is least sure of."""
    storage = Storage.open(args.home)
    profile = storage.load_profile()
    if profile is None:
        out.say(
            f"No profile at {storage.profile_path}. Run `llmtone init` first -- "
            "calibration works out what to ask from what you already have."
        )
        return EXIT_ERROR

    records = storage.evidence()
    asked = answered_question_ids(records)
    chosen = select_questions(profile, asked_ids=asked, count=args.count)
    pairs = select_pairs(
        profile, asked_ids=answered_pair_ids(records), count=args.pairs
    )

    out.say(out.bold("llmtone calibrate"))
    priority = dimension_priority(profile, asked)
    weakest = sorted(priority.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    out.say(
        "Chasing: "
        + ", ".join(
            f"{name} (conf {profile.style[name].confidence:.2f})"
            for name, _ in weakest
            if name in profile.style
        )
    )
    out.say(out.dim("Still on this machine. Still no network code."))
    out.say()

    if args.count <= 0 and args.pairs <= 0:
        out.say("Nothing to ask: both -n and --pairs are zero.")
        return EXIT_OK

    if not chosen and not pairs:
        out.say(
            "You've answered everything in the bank. Feed it real writing "
            "instead: `llmtone analyse --save FILE`."
        )
        return EXIT_OK

    if not chosen and args.count > 0:
        out.say(
            out.dim("No written questions left in the bank -- word choices only.")
        )
        out.say()

    if args.dry_run:
        out.say(out.bold(f"Would ask {len(chosen)}:"))
        out.say()
        for candidate in chosen:
            out.say(out.cyan(f"  {candidate.question.text}"))
            out.say(out.dim(f"    for: {candidate.reason()}"))
            out.say()
        if pairs:
            out.say(out.bold(f"Then {len(pairs)} word choices:"))
            out.say()
            for pair in pairs:
                # The id is printed so that a --choices file can be written
                # against exactly the pairs this round would offer.
                out.say(
                    out.cyan(f"  {pair.formal} or {pair.plain}?")
                    + out.dim(f"   ({pair.id})")
                )
            out.say()
        return EXIT_OK

    scripted = _read_answers_file(Path(args.answers)) if args.answers else None
    scripted_choices = (
        _read_answers_file(Path(args.choices)) if args.choices else None
    )

    seq = len(records)
    before = _confidences(profile)
    before_avoid = list(profile.notes.get("avoid_confirmed_by_choice", []))
    answered = 0
    for candidate in chosen:
        question = candidate.question
        out.say(out.cyan(question.text))
        out.say(out.dim(f"  asking because: {candidate.reason()}"))
        if scripted is not None:
            answer = scripted.get(question.id, "")
            if answer:
                out.say(out.dim(f"  (from {args.answers})"))
        else:
            answer = _prompt_multiline(out, f"  {question.hint} (blank line to finish)")
        if not answer.strip():
            out.say(out.dim("  skipped"))
            out.say()
            continue
        words = len(answer.split())
        if words < MIN_ANSWER_WORDS:
            out.say(out.dim(f"  noted ({words} words -- a bit short, but fine)"))
        record_calibration(storage, question, answer, seq)
        seq += 1
        answered += 1
        out.say()

    answered += _run_pairs(storage, out, pairs, scripted_choices, seq + answered)

    if not answered:
        out.say("Nothing answered, nothing changed.")
        return EXIT_OK

    _rebuild(storage, out)
    updated = storage.load_profile()
    if updated is not None:
        out.say()
        confirmed = [
            word for word in updated.notes.get("avoid_confirmed_by_choice", [])
            if word not in before_avoid
        ]
        if confirmed:
            out.say(out.bold("Now evidence rather than guesswork"))
            out.say()
            out.say(f"  Avoid: {', '.join(confirmed)}")
            out.say()
        _report_movement(out, before, _confidences(updated))
    return EXIT_OK


def cmd_not_yet(args: argparse.Namespace, out: Out) -> int:
    out.say(_NOT_YET_MESSAGE.format(name=args.command))
    return EXIT_NOT_YET


# --- argument parsing -------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmtone",
        description="One voice. Any AI. A local-first writing profile.",
    )
    parser.add_argument("--version", action="version", version=f"llmtone {__version__}")
    parser.add_argument(
        "--home",
        default=None,
        help="Override the llmtone directory (default: ~/.llmtone).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Build a profile from scratch.")
    init.add_argument("--force", action="store_true", help="Overwrite an existing profile.")
    init.add_argument("--answers", help="JSON file of question id -> answer (non-interactive).")
    init.add_argument(
        "--sample",
        action="append",
        metavar="FILE[:CONTEXT]",
        help="File containing a real writing sample. Repeatable, and a "
             ":CONTEXT suffix labels it -- e.g. --sample emails.txt:business "
             f"--sample launch.md:marketing. Presets: {', '.join(PRESET_CONTEXTS)}.",
    )
    init.set_defaults(func=cmd_init)

    analyse_cmd = subparsers.add_parser("analyse", aliases=["analyze"], help="Analyse one file.")
    analyse_cmd.add_argument("file")
    analyse_cmd.add_argument("--json", action="store_true", help="Full metric dump as JSON.")
    analyse_cmd.add_argument("--save", action="store_true", help="Add this file to your profile.")
    analyse_cmd.add_argument(
        "--context",
        metavar="LABEL",
        help="Where this was written -- work, casual, whatever you call it. "
             "Used with --save to build a per-context profile.",
    )
    analyse_cmd.set_defaults(func=cmd_analyse)

    profile_cmd = subparsers.add_parser("profile", help="Show your profile.")
    profile_cmd.set_defaults(func=cmd_profile)

    prompt_cmd = subparsers.add_parser("prompt", help="Writing instructions for any model.")
    prompt_cmd.add_argument(
        "--context",
        metavar="LABEL",
        help="Instructions for how you write in one context.",
    )
    prompt_cmd.add_argument(
        "--write",
        nargs="?",
        const=DEFAULT_TARGET,
        metavar="FILE",
        help=(
            f"Splice the instructions into {DEFAULT_TARGET} (or FILE), "
            "replacing what an earlier run put there."
        ),
    )
    prompt_cmd.set_defaults(func=cmd_prompt)

    export_cmd = subparsers.add_parser("export", help="Export profile.json.")
    export_cmd.add_argument("-o", "--output", help="Write to a file instead of stdout.")
    export_cmd.set_defaults(func=cmd_export)

    calibrate_cmd = subparsers.add_parser(
        "calibrate", help="More questions, chosen by what is least certain."
    )
    calibrate_cmd.add_argument(
        "-n", "--count", type=int, default=DEFAULT_ROUND,
        help=f"How many questions to ask (default {DEFAULT_ROUND}).",
    )
    calibrate_cmd.add_argument(
        "--pairs", type=int, default=DEFAULT_PAIRS,
        help=(
            f"How many A/B word choices to offer (default {DEFAULT_PAIRS}, "
            "0 for none)."
        ),
    )
    calibrate_cmd.add_argument(
        "--answers", help="JSON file of question id -> answer (non-interactive)."
    )
    calibrate_cmd.add_argument(
        "--choices", help="JSON file of pair id -> chosen word (non-interactive)."
    )
    calibrate_cmd.add_argument(
        "--dry-run", action="store_true",
        help="Show what it would ask, and why, without asking or writing.",
    )
    calibrate_cmd.set_defaults(func=cmd_calibrate)

    check_cmd = subparsers.add_parser(
        "check", help="Check text against your profile (Phase 3)."
    )
    check_cmd.add_argument("file", nargs="?")
    check_cmd.set_defaults(func=cmd_not_yet)

    return parser


def _prefer_utf8(stream) -> None:
    """Ask the stream for UTF-8, and never fail on an unencodable character.

    Windows terminals default to a legacy code page. Without this, a single
    block character or curly quote ends the program with a UnicodeEncodeError
    in the middle of printing a profile.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):  # pragma: no cover - platform dependent
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _prefer_utf8(sys.stdout)
    out = Out()
    if args.command in ("analyze",):
        args.command = "analyse"
    try:
        return args.func(args, out)
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        out.say("\nStopped. Nothing was lost; evidence is written as you go.")
        return EXIT_ERROR
    except (OSError, ValueError) as error:
        # Deliberately prints the error, never the writing that caused it.
        out.say(f"llmtone: {error}")
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
