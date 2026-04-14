import re
from dataclasses import dataclass, field
from enum import Enum


class PartType(Enum):
    THEORY  = "theory"
    CODE    = "code"
    DIAGRAM = "diagram"


@dataclass
class QuestionPart:
    text:       str
    part_type:  PartType
    marks:      int
    part_index: int       # 0-based position in question


@dataclass
class SplitResult:
    parts:         list[QuestionPart]
    marks_unknown: bool   # True when total marks were not detected from the PDF


# Patterns that signal a code part
CODE_SIGNALS = re.compile(
    r"\b(write\s+a?\s*(c#?|java|c\+\+|python|program|code)"
    r"|implement|develop\s+a\s+program"
    r"|create\s+a\s+(class|method|function|program)"
    r"|illustrate\s+with\s+(a\s+)?program)\b",
    re.IGNORECASE,
)

# Patterns that signal a diagram part
DIAGRAM_SIGNALS = re.compile(
    r"\b(draw|diagram|sketch|illustrate\s+with\s+(a\s+)?diagram"
    r"|show\s+(with\s+)?(a\s+)?figure|with\s+suitable\s+diagram)\b",
    re.IGNORECASE,
)

# Marks breakdown pattern: [1+4], [2+3+5], (3+2+5)
MARKS_BREAKDOWN = re.compile(r"[\[\(](\d+(?:\+\d+)+)[\]\)]")

# Inline total marks pattern: [5], (10), [3 marks], (2 marks)
TOTAL_MARKS_PATTERN = re.compile(r"[\[\(](\d+)(?:\s*marks?)?[\]\)]", re.IGNORECASE)

# Sentence splitter for detecting part boundaries
PART_SPLITTER = re.compile(r"(?<=[.?])\s+(?=[A-Z])")

# Sentinel used when marks are not known — caller must replace before scoring
MARKS_UNKNOWN_SENTINEL = -1


def classify_part(text: str) -> PartType:
    if DIAGRAM_SIGNALS.search(text):
        return PartType.DIAGRAM
    if CODE_SIGNALS.search(text):
        return PartType.CODE
    return PartType.THEORY


def extract_mark_weights(question_text: str, total_marks: int) -> list[int] | None:
    """
    Extract per-part marks from breakdown notation like [1+4] or [3+2+5].
    Returns None if no breakdown found — caller handles fallback.
    """
    match = MARKS_BREAKDOWN.search(question_text)
    if match:
        parts = [int(x) for x in match.group(1).split("+")]
        if sum(parts) == total_marks:
            return parts
    return None


def detect_total_marks(question_text: str) -> int | None:
    """
    Try to extract a standalone total marks value from the question text,
    e.g. [5], (10), [3 marks].
    Returns None if nothing is found.
    """
    # Don't match breakdown patterns like [1+4]
    for match in TOTAL_MARKS_PATTERN.finditer(question_text):
        return int(match.group(1))
    return None


def split_question_into_parts(
    question_text: str,
    total_marks: int,
) -> SplitResult:
    """
    Split a question into typed parts with mark weights.
    Returns a SplitResult that includes a marks_unknown flag when the
    total_marks value was not detected from the PDF (i.e. is the sentinel -1).

    Handles:
    - Single-type questions: "Explain virtualization" → [THEORY, N]
    - Mixed questions: "Define X. Write a program. [1+4]" → [THEORY 1, CODE 4]
    - Sub-lettered: "a) ... b) ..." → splits on letter markers
    """
    marks_unknown = (total_marks == MARKS_UNKNOWN_SENTINEL)

    # If marks are unknown, use 0 as placeholder — frontend will fill real value
    effective_marks = 0 if marks_unknown else total_marks

    # Clean marks breakdown from text before splitting
    clean_text = MARKS_BREAKDOWN.sub("", question_text).strip()
    clean_text = TOTAL_MARKS_PATTERN.sub("", clean_text).strip()

    # Try splitting on sub-letter markers first: a), b), c)
    sub_parts = re.split(r"\n?\s*[a-d]\)\s*", clean_text)
    sub_parts = [p.strip() for p in sub_parts if p.strip()]

    # If no sub-letters, split on sentence boundaries
    if len(sub_parts) <= 1:
        sub_parts = [s.strip() for s in PART_SPLITTER.split(clean_text) if s.strip()]

    # If still one part, return as single
    if len(sub_parts) <= 1:
        part_type = classify_part(clean_text)
        return SplitResult(
            parts=[QuestionPart(
                text=clean_text,
                part_type=part_type,
                marks=effective_marks,
                part_index=0,
            )],
            marks_unknown=marks_unknown,
        )

    # Get mark weights
    mark_weights = extract_mark_weights(question_text, effective_marks) if not marks_unknown else None
    if not mark_weights or len(mark_weights) != len(sub_parts):
        if marks_unknown:
            mark_weights = [0] * len(sub_parts)
        else:
            per_part  = effective_marks // len(sub_parts)
            remainder = effective_marks % len(sub_parts)
            mark_weights = [per_part] * len(sub_parts)
            mark_weights[-1] += remainder

    return SplitResult(
        parts=[
            QuestionPart(
                text=part_text,
                part_type=classify_part(part_text),
                marks=mark_weights[i] if i < len(mark_weights) else 0,
                part_index=i,
            )
            for i, part_text in enumerate(sub_parts)
        ],
        marks_unknown=marks_unknown,
    )