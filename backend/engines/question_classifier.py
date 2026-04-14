import re
from dataclasses import dataclass
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

# Sentence splitter for detecting part boundaries
PART_SPLITTER = re.compile(r"(?<=[.?])\s+(?=[A-Z])")


def classify_part(text: str) -> PartType:
    if DIAGRAM_SIGNALS.search(text):
        return PartType.DIAGRAM
    if CODE_SIGNALS.search(text):
        return PartType.CODE
    return PartType.THEORY


def extract_mark_weights(question_text: str, total_marks: int) -> list[int]:
    """
    Extract per-part marks from breakdown notation like [1+4] or [3+2+5].
    Falls back to equal distribution if no breakdown found.
    """
    match = MARKS_BREAKDOWN.search(question_text)
    if match:
        parts = [int(x) for x in match.group(1).split("+")]
        if sum(parts) == total_marks:
            return parts
    return None  # caller handles fallback


def split_question_into_parts(
    question_text: str,
    total_marks: int,
) -> list[QuestionPart]:
    """
    Split a question into typed parts with mark weights.
    
    Handles:
    - Single-type questions: "Explain virtualization" → [THEORY, 5]
    - Mixed questions: "Define X. Write a program. [1+4]" → [THEORY 1, CODE 4]
    - Sub-lettered: "a) ... b) ..." → splits on letter markers
    """
    # Clean marks breakdown from text before splitting
    clean_text = MARKS_BREAKDOWN.sub("", question_text).strip()

    # Try splitting on sub-letter markers first: a), b), c)
    sub_parts = re.split(r"\n?\s*[a-d]\)\s*", clean_text)
    sub_parts = [p.strip() for p in sub_parts if p.strip()]

    # If no sub-letters, split on sentence boundaries
    if len(sub_parts) <= 1:
        sub_parts = [s.strip() for s in PART_SPLITTER.split(clean_text) if s.strip()]

    # If still one part, return as single
    if len(sub_parts) <= 1:
        part_type = classify_part(clean_text)
        return [QuestionPart(
            text=clean_text,
            part_type=part_type,
            marks=total_marks,
            part_index=0,
        )]

    # Get mark weights
    mark_weights = extract_mark_weights(question_text, total_marks)
    if not mark_weights or len(mark_weights) != len(sub_parts):
        # Equal distribution fallback
        per_part = total_marks // len(sub_parts)
        remainder = total_marks % len(sub_parts)
        mark_weights = [per_part] * len(sub_parts)
        mark_weights[-1] += remainder  # give remainder to last part

    return [
        QuestionPart(
            text=part_text,
            part_type=classify_part(part_text),
            marks=mark_weights[i] if i < len(mark_weights) else 0,
            part_index=i,
        )
        for i, part_text in enumerate(sub_parts)
    ]