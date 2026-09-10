"""Turn a profile into words: one summary for you, one for a model.

Both renderers are deterministic template assembly. No model is involved, and
neither renderer invents anything the profile does not contain.

The rule both follow: a dimension below :data:`CONFIDENCE_THRESHOLD` is not
stated as a fact. The summary lists it separately as not yet established, and
the instructions leave it out entirely -- telling a model "be quite funny" on
0.3 confidence is worse than saying nothing.
"""

from __future__ import annotations

from .model import VoiceProfile

__all__ = [
    "CONFIDENCE_THRESHOLD",
    "render_summary",
    "render_instructions",
    "describe_dimension",
]

#: Below this, a dimension is an impression, not an observation.
CONFIDENCE_THRESHOLD = 0.45

#: Readable names for punctuation marks. "You never use question" is not a
#: sentence; "you never use question marks" is.
MARK_LABELS: dict[str, str] = {
    "comma": "commas",
    "period": "full stops",
    "semicolon": "semicolons",
    "colon": "colons",
    "parentheses": "parentheses",
    "em_dash": "em dashes",
    "en_dash": "en dashes",
    "hyphen": "hyphens",
    "exclamation": "exclamation marks",
    "question": "question marks",
    "ellipsis": "ellipses",
    "quote": "quotation marks",
}


def _mark_label(mark: str) -> str:
    return MARK_LABELS.get(mark, mark.replace("_", " "))

#: dimension -> ((max_value, phrase), ...) in ascending order.
_PHRASES: dict[str, tuple[tuple[int, str], ...]] = {
    "formality": (
        (20, "very casual"),
        (40, "casual"),
        (60, "neither formal nor casual"),
        (80, "fairly formal"),
        (100, "formal"),
    ),
    "directness": (
        (20, "very indirect"),
        (40, "inclined to soften things"),
        (60, "reasonably direct"),
        (80, "direct"),
        (100, "very direct"),
    ),
    "warmth": (
        (20, "quite detached"),
        (40, "matter-of-fact"),
        (60, "moderately warm"),
        (80, "warm"),
        (100, "very warm"),
    ),
    "conciseness": (
        (20, "expansive"),
        (40, "fairly expansive"),
        (60, "middling in length"),
        (80, "concise"),
        (100, "very concise"),
    ),
    "humour": (
        (20, "straight-faced"),
        (40, "occasionally light"),
        (60, "moderately playful"),
        (80, "playful"),
        (100, "very playful"),
    ),
    "hedging": (
        (20, "unhedged"),
        (40, "rarely hedges"),
        (60, "hedges sometimes"),
        (80, "hedges often"),
        (100, "hedges heavily"),
    ),
    "technicality": (
        (20, "non-technical"),
        (40, "lightly technical"),
        (60, "moderately technical"),
        (80, "technical"),
        (100, "highly technical"),
    ),
    "conversationality": (
        (20, "written rather than spoken"),
        (40, "fairly written"),
        (60, "between written and spoken"),
        (80, "conversational"),
        (100, "very conversational"),
    ),
}


def describe_dimension(name: str, value: int) -> str:
    for threshold, phrase in _PHRASES.get(name, ()):
        if value <= threshold:
            return phrase
    return f"{name} {value}"


def _established(profile: VoiceProfile) -> dict[str, int]:
    return {
        name: score.value
        for name, score in profile.style.items()
        if score.confidence >= CONFIDENCE_THRESHOLD
    }


def _join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def render_summary(profile: VoiceProfile) -> str:
    """A short prose description of how this person writes."""
    established = _established(profile)
    lines: list[str] = []

    if not established:
        lines.append(
            "There isn't enough writing yet to describe your voice with any "
            "confidence. Add another sample or two with `llmtone analyse "
            "--save <file>`."
        )
    else:
        headline = [
            describe_dimension(name, value)
            for name, value in list(established.items())[:3]
        ]
        lines.append(f"You're {_join(headline)}.")

        detail: list[str] = []
        syntax = profile.syntax
        contraction = syntax.get("contraction_preference", 0.0)
        if contraction >= 0.5:
            detail.append("You use contractions naturally")
        elif contraction <= 0.15:
            detail.append("You rarely contract")

        avg = syntax.get("average_sentence_length", 0.0)
        variance = syntax.get("sentence_length_variance", 0.0)
        if avg:
            varies = "and vary their length a lot" if variance >= 60 else \
                     "and keep them fairly even in length" if variance <= 20 else \
                     "with some variation in length"
            detail.append(
                f"your sentences average about {avg:.0f} words {varies}"
            )

        paragraph = profile.structure.get("paragraph_length")
        if paragraph:
            detail.append(f"your paragraphs are {paragraph}")

        if profile.structure.get("bullet_preference") == "high":
            detail.append("you reach for bullet points readily")

        if detail:
            lines.append(_join(detail).capitalize().rstrip(".") + ".")

        rare = [
            _mark_label(mark)
            for mark, freq in sorted(profile.punctuation.items())
            if freq == "never"
        ]
        if rare:
            lines.append(f"You never use: {_join(rare)}.")

    unsure = [
        name for name, score in profile.style.items()
        if score.confidence < CONFIDENCE_THRESHOLD
    ]
    if unsure:
        lines.append(
            "Not yet confident about: " + _join(sorted(unsure))
            + ". More writing, or the calibration questions, will settle these."
        )

    prefer = profile.vocabulary.get("prefer", [])
    avoid = profile.vocabulary.get("avoid", [])
    confirmed = set(profile.notes.get("avoid_confirmed_by_choice", []))
    if prefer:
        lines.append("\nPrefer\n" + "\n".join(f"  - {w}" for w in prefer))
    if avoid:
        block = ["\nAvoid"]
        for word in avoid:
            mark = "" if word in confirmed else "  ?"
            block.append(f"  - {word}{mark}")
        guessed = [w for w in avoid if w not in confirmed]
        if guessed:
            block.append(
                "  ? inferred from what you never write, so treat as a hint"
            )
        lines.append("\n".join(block))
    return "\n".join(lines)


def render_instructions(profile: VoiceProfile) -> str:
    """Model-independent writing instructions.

    Describes writing behaviour only. It does not claim to describe a person,
    and it explicitly tells the model not to copy source text.
    """
    established = _established(profile)
    out: list[str] = ["Write in this person's voice. Their observed habits:", ""]

    if not established:
        out.append(
            "- Not enough is known about their writing yet. Write plainly and "
            "avoid affectation."
        )
    for name, value in established.items():
        out.append(f"- {describe_dimension(name, value).capitalize()}.")

    syntax = profile.syntax
    avg = syntax.get("average_sentence_length")
    if avg:
        out.append(
            f"- Sentences average around {avg:.0f} words. "
            + (
                "Vary their length noticeably."
                if syntax.get("sentence_length_variance", 0) >= 60
                else "Keep their length fairly even."
            )
        )

    contraction = syntax.get("contraction_preference", 0.0)
    if contraction >= 0.5:
        out.append("- Use contractions naturally.")
    elif contraction <= 0.15:
        out.append("- Avoid contractions.")

    if syntax.get("fragment_preference", 0) >= 0.10:
        out.append("- Occasional sentence fragments are in character.")
    if syntax.get("passive_preference", 0) <= 0.10:
        out.append("- Prefer active voice.")

    structure = profile.structure
    if structure.get("paragraph_length"):
        out.append(f"- Keep paragraphs {structure['paragraph_length']}.")
    if structure.get("bullet_preference") == "high":
        out.append("- Bullet points are welcome.")
    elif structure.get("bullet_preference") == "low":
        out.append("- Prefer prose over bullet points.")
    if structure.get("heading_preference") == "low":
        out.append("- Use few or no headings.")

    never = [
        _mark_label(mark)
        for mark, freq in sorted(profile.punctuation.items())
        if freq == "never"
    ]
    frequent = [
        _mark_label(mark)
        for mark, freq in sorted(profile.punctuation.items())
        if freq == "frequent"
    ]
    if never:
        out.append(f"- Do not use: {_join(never)}.")
    if frequent:
        out.append(f"- They use {_join(frequent)} freely.")

    prefer = profile.vocabulary.get("prefer", [])
    avoid = profile.vocabulary.get("avoid", [])
    confirmed = [
        word for word in avoid
        if word in set(profile.notes.get("avoid_confirmed_by_choice", []))
    ]
    guessed = [word for word in avoid if word not in confirmed]
    phrases = profile.phrasing.get("preferred", [])
    if prefer:
        out.append(f"- Vocabulary they reach for: {', '.join(prefer)}.")
    if phrases:
        out.append(f"- Turns of phrase they use: {', '.join(phrases)}.")
    if confirmed:
        out.append(
            f"- They chose against these words when asked directly, so never "
            f"use them: {', '.join(confirmed)}."
        )
    if guessed:
        out.append(
            f"- Words absent from their writing, so probably avoid: "
            f"{', '.join(guessed)}."
        )
    technical = profile.vocabulary.get("technical_terms", [])
    if technical:
        out.append(
            f"- Domain vocabulary they use without explaining: "
            f"{', '.join(technical[:8])}."
        )

    out += [
        "",
        "Constraints:",
        "- Do not imitate or copy any source text literally.",
        "- Do not add introductions or conclusions that were not asked for.",
        "- The result should read as naturally written, not polished into "
        "uniformity.",
        "- These are writing habits, not personality traits. Do not "
        "role-play a persona.",
    ]
    return "\n".join(out)
