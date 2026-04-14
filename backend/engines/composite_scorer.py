from dataclasses import dataclass
from engines.question_classifier import QuestionPart, PartType, split_question_into_parts
from engines.keyword_engine import keyword_score, KeywordResult
from engines.sbert_engine import sbert_score, SBERTResult
from engines.rag_engine import rag_score, RAGResult, ReferenceIndex

# ── Weight profiles ───────────────────────────────────────────────────────────

WEIGHTS_WITH_RAG = {
    "keyword": 0.20,
    "sbert":   0.30,
    "rag":     0.40,
    "length":  0.10,
}

WEIGHTS_WITHOUT_RAG = {
    "keyword": 0.10,
    "sbert":   0.75,
    "rag":     0.00,
    "length":  0.15,
}


@dataclass
class PartScore:
    part_index:  int
    part_type:   str
    marks:       int
    raw_score:   float       # 0.0 – 1.0
    final_marks: float       # scaled to part marks
    keyword_score:   float
    sbert_score:     float
    rag_score:       float | None
    length_score:    float
    missed_concepts: list[str]
    feedback_flags:  list[str]  # e.g. ["too_short", "low_keyword_coverage"]


@dataclass
class CompositeResult:
    question_id:   int
    max_marks:     int
    final_marks:   float        # rounded to 1dp
    percentage:    float
    parts:         list[PartScore]
    overall_gaps:  list[str]
    feedback:      list[str]    # human-readable feedback lines


# ── Length signal ─────────────────────────────────────────────────────────────

def length_signal(answer: str, max_marks: int) -> float:
    """
    Soft signal — penalizes very short answers.
    Expected: ~25 words per mark (university baseline).
    Caps at 1.0 so verbose answers aren't rewarded beyond full credit.
    """
    if not answer.strip():
        return 0.0
    words = len(answer.split())
    expected = max_marks * 25
    return min(words / expected, 1.0)


# ── Floor enforcement ─────────────────────────────────────────────────────────

def enforce_floor(answer: str, score: float) -> float:
    """Blank or near-blank answers always score zero regardless of engine outputs."""
    if len(answer.strip().split()) < 5:
        return 0.0
    return score


# ── Theory part scorer ────────────────────────────────────────────────────────

def score_theory_part(
    part: QuestionPart,
    student_answer: str,
    all_question_texts: list[str],
    question_index: int,
    index: ReferenceIndex | None,
    has_reference: bool,
) -> PartScore:

    flags = []

    kw: KeywordResult = keyword_score(
        question_text=part.text,
        student_answer=student_answer,
        all_question_texts=all_question_texts,
        question_index=question_index,
    )

    sb: SBERTResult = sbert_score(
        question_text=part.text,
        student_answer=student_answer,
    )

    rg: RAGResult | None = None
    if has_reference and index:
        rg = rag_score(
            question_text=part.text,
            student_answer=student_answer,
            index=index,
        )

    ls = length_signal(student_answer, part.marks)

    weights = WEIGHTS_WITH_RAG if (has_reference and rg) else WEIGHTS_WITHOUT_RAG

    raw = (
        kw.score   * weights["keyword"] +
        sb.score   * weights["sbert"]   +
        (rg.score if rg else 0.0) * weights["rag"] +
        ls         * weights["length"]
    )

    raw = enforce_floor(student_answer, raw)

    # Feedback flags
    if ls < 0.4:
        flags.append("too_short")
    if kw.score < 0.3:
        flags.append("low_keyword_coverage")
    if sb.score < 0.4:
        flags.append("low_conceptual_similarity")

    return PartScore(
        part_index=part.part_index,
        part_type=part.part_type.value,
        marks=part.marks,
        raw_score=round(raw, 4),
        final_marks=round(raw * part.marks, 1),
        keyword_score=kw.score,
        sbert_score=sb.score,
        rag_score=rg.score if rg else None,
        length_score=ls,
        missed_concepts=rg.gaps if rg else kw.missed,
        feedback_flags=flags,
    )


# ── Code part scorer ──────────────────────────────────────────────────────────

def score_code_part(part: QuestionPart, student_answer: str) -> PartScore:
    """
    Routes to code-specific scoring.
    Currently: keyword/construct check + length signal.
    Phase 8 extension: add syntax check + output verification.
    """
    flags = []

    # Detect required constructs from the question text
    # These are rough heuristics — Phase 8 can make this question-specific
    import re
    constructs = re.findall(
        r"\b(class|interface|method|constructor|loop|recursion|"
        r"overload|override|delegate|LINQ|exception|try|catch|"
        r"static|abstract|virtual|async|await|struct|enum)\b",
        part.text,
        re.IGNORECASE,
    )
    constructs = list(set(c.lower() for c in constructs))

    answer_lower = student_answer.lower()
    matched = [c for c in constructs if c in answer_lower]
    construct_score = len(matched) / len(constructs) if constructs else 0.5

    ls = length_signal(student_answer, part.marks)

    # SBERT still runs — catches conceptual proximity
    sb: SBERTResult = sbert_score(
        question_text=part.text,
        student_answer=student_answer,
    )

    raw = (
        construct_score * 0.45 +
        sb.score        * 0.35 +
        ls              * 0.20
    )

    raw = enforce_floor(student_answer, raw)

    missed_constructs = [c for c in constructs if c not in answer_lower]

    if ls < 0.4:
        flags.append("code_too_short")
    if missed_constructs:
        flags.append(f"missing_constructs:{','.join(missed_constructs)}")

    return PartScore(
        part_index=part.part_index,
        part_type=part.part_type.value,
        marks=part.marks,
        raw_score=round(raw, 4),
        final_marks=round(raw * part.marks, 1),
        keyword_score=construct_score,
        sbert_score=sb.score,
        rag_score=None,
        length_score=ls,
        missed_concepts=missed_constructs,
        feedback_flags=flags,
    )


# ── Main composite function ───────────────────────────────────────────────────

def compute_composite(
    question_id:         int,
    question_text:       str,
    student_answer:      str,
    max_marks:           int,
    all_question_texts:  list[str],
    question_index:      int,
    index:               ReferenceIndex | None,
    has_reference:       bool,
) -> CompositeResult:

    parts = split_question_into_parts(question_text, max_marks)

    # For single-part questions the whole answer goes to that part
    # For multi-part questions we need to split the student answer too
    # Simple split: divide answer proportionally by part mark weight
    # Phase 8 can add smarter answer-to-part alignment
    if len(parts) == 1:
        answer_segments = [student_answer]
    else:
        answer_segments = split_answer_by_parts(student_answer, parts)

    part_scores: list[PartScore] = []

    for i, part in enumerate(parts):
        seg = answer_segments[i] if i < len(answer_segments) else ""

        if part.part_type == PartType.CODE:
            ps = score_code_part(part, seg)
        else:
            # Both THEORY and DIAGRAM use theory pipeline
            # DIAGRAM adds image input in Phase 8
            ps = score_theory_part(
                part=part,
                student_answer=seg,
                all_question_texts=all_question_texts,
                question_index=question_index,
                index=index,
                has_reference=has_reference,
            )
        part_scores.append(ps)

    # Weighted final marks
    total_final = sum(ps.final_marks for ps in part_scores)
    total_final = round(min(total_final, max_marks), 1)
    percentage  = round((total_final / max_marks) * 100, 1) if max_marks > 0 else 0.0

    # Aggregate gaps and feedback
    all_gaps = []
    all_feedback = []
    for ps in part_scores:
        all_gaps.extend(ps.missed_concepts)
        for flag in ps.feedback_flags:
            all_feedback.append(flag_to_message(flag, ps.part_type, ps.part_index))

    return CompositeResult(
        question_id=question_id,
        max_marks=max_marks,
        final_marks=total_final,
        percentage=percentage,
        parts=part_scores,
        overall_gaps=list(set(all_gaps)),
        feedback=all_feedback,
    )


def split_answer_by_parts(answer: str, parts: list[QuestionPart]) -> list[str]:
    """
    Attempt to split a student's answer into segments matching question parts.
    Looks for natural boundaries — blank lines, numbered markers, 'a)', 'b)' etc.
    Falls back to proportional word split if no markers found.
    """
    # Try marker-based split
    marker_split = re.split(r"\n\s*(?:[a-d]\)|Q?\d+\.)\s*", answer)
    marker_split = [s.strip() for s in marker_split if s.strip()]

    if len(marker_split) == len(parts):
        return marker_split

    # Proportional word split fallback
    words = answer.split()
    total_marks = sum(p.marks for p in parts)
    result = []
    start = 0
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            result.append(" ".join(words[start:]))
        else:
            count = int(len(words) * (part.marks / total_marks))
            result.append(" ".join(words[start:start + count]))
            start += count
    return result


def flag_to_message(flag: str, part_type: str, part_index: int) -> str:
    part_label = f"Part {chr(97 + part_index).upper()}"
    messages = {
        "too_short":               f"{part_label}: Answer appears too brief for the marks allocated.",
        "low_keyword_coverage":    f"{part_label}: Key concepts from the question are missing.",
        "low_conceptual_similarity": f"{part_label}: Answer may not address the question directly.",
        "code_too_short":          f"{part_label}: Code answer is very short — ensure the full program is included.",
    }
    if flag.startswith("missing_constructs:"):
        constructs = flag.split(":")[1]
        return f"{part_label}: Code may be missing: {constructs}."
    return messages.get(flag, f"{part_label}: {flag}")