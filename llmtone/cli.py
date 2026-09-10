"""The llmtone command line.

    llmtone init          five questions, then a real writing sample
    llmtone analyse FILE  metrics for one file
    llmtone profile       your profile, as bars and prose
    llmtone prompt        model-independent writing instructions
    llmtone export        the profile as JSON
    llmtone calibrate     (Phase 2)
    llmtone check FILE    (Phase 2)

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
from .calibration import ONBOARDING_QUESTIONS, record_response, record_sample
from .calibration.questions import MIN_ANSWER_WORDS
from .evidence import utc_now
from .profile import (
    Storage,
    build_profile,
    render_instructions,
    render_summary,
)
from .scoring import DIMENSIONS

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NOT_YET = 2

_PHASE_2_MESSAGE = (
    "`llmtone {name}` lands in Phase 2. Phase 1 covers init, analyse, "
    "profile, prompt and export."
)


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
    texts = storage.sample_texts()
    existing = storage.load_profile()
    profile = build_profile(
        texts,
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
        except EOFError:
            break
        if not line.strip() and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip()


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

    out.say(out.bold("llmtone init"))
    out.say(
        "Five questions, then something you've actually written.\n"
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

    out.say(out.bold("Now something you've actually written."))
    out.say(
        "An email, a Slack message, some documentation, a forum post -- "
        "anything real.\n"
        + out.yellow("Don't rewrite it first. We want to see how you actually write.")
        + "\n"
    )

    if args.sample:
        sample_path = Path(args.sample)
        text = sample_path.read_text(encoding="utf-8")
        out.say(out.dim(f"  read {len(text.split())} words from {sample_path}"))
    else:
        text = _prompt_multiline(
            out, "  Paste it below, then a blank line. Or press Enter to skip."
        )

    if text.strip():
        record_sample(storage, text, source=args.sample or "pasted", seq=seq)
    elif answered == 0:
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
        record_sample(storage, text, source=str(path), seq=len(storage.evidence()))
        out.say()
        _rebuild(storage, out)
    return EXIT_OK


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


def cmd_prompt(args: argparse.Namespace, out: Out) -> int:
    profile = _require_profile(args, out)
    if profile is None:
        return EXIT_ERROR
    out.say(render_instructions(profile))
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


def cmd_not_yet(args: argparse.Namespace, out: Out) -> int:
    out.say(_PHASE_2_MESSAGE.format(name=args.command))
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
    init.add_argument("--sample", help="File containing a real writing sample.")
    init.set_defaults(func=cmd_init)

    analyse_cmd = subparsers.add_parser("analyse", aliases=["analyze"], help="Analyse one file.")
    analyse_cmd.add_argument("file")
    analyse_cmd.add_argument("--json", action="store_true", help="Full metric dump as JSON.")
    analyse_cmd.add_argument("--save", action="store_true", help="Add this file to your profile.")
    analyse_cmd.set_defaults(func=cmd_analyse)

    profile_cmd = subparsers.add_parser("profile", help="Show your profile.")
    profile_cmd.set_defaults(func=cmd_profile)

    prompt_cmd = subparsers.add_parser("prompt", help="Writing instructions for any model.")
    prompt_cmd.set_defaults(func=cmd_prompt)

    export_cmd = subparsers.add_parser("export", help="Export profile.json.")
    export_cmd.add_argument("-o", "--output", help="Write to a file instead of stdout.")
    export_cmd.set_defaults(func=cmd_export)

    for name, help_text in (
        ("calibrate", "Adaptive calibration questions (Phase 2)."),
        ("check", "Check text against your profile (Phase 2)."),
    ):
        stub = subparsers.add_parser(name, help=help_text)
        if name == "check":
            stub.add_argument("file", nargs="?")
        stub.set_defaults(func=cmd_not_yet)

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
