import re
from dataclasses import dataclass
from engines.question_classifier import (
    QuestionPart, PartType, SplitResult, split_question_into_parts,
    MARKS_UNKNOWN_SENTINEL,
)
from engines.keyword_engine import keyword_score, KeywordResult
from engines.sbert_engine import sbert_score, SBERTResult
from engines.rag_engine import rag_score, RAGResult, ReferenceIndex
from engines.nli_engine import contradiction_penalty, extract_key_sentences
from engines.code_engine import score_code, CodeResult
from engines.diagram_engine import extract_diagram_text, merge_answer_with_diagram


# ── Weight profiles ────────────────────────────────────────────────────────────

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

# When there is no reference AND the question has code signals,
# SBERT is a poor judge of code quality — shift weight to keyword/length
WEIGHTS_WITHOUT_RAG_CODE_HEAVY = {
    "keyword": 0.40,
    "sbert":   0.40,
    "rag":     0.00,
    "length":  0.20,
}


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class PartScore:
    part_index:           int
    part_type:            str
    marks:                int
    raw_score:            float
    final_marks:          float
    keyword_score:        float
    sbert_score:          float
    rag_score:            float | None
    length_score:         float
    contradiction_score:  float | None
    missed_concepts:      list[str]
    feedback_flags:       list[str]


@dataclass
class CompositeResult:
    question_id:  int
    max_marks:    int
    final_marks:  float
    percentage:   float
    parts:        list[PartScore]
    overall_gaps: list[str]
    feedback:     list[str]


# ── Helpers ────────────────────────────────────────────────────────────────────

def length_signal(answer: str, max_marks: int) -> float:
    if not answer.strip() or max_marks <= 0:
        return 0.0
    words    = len(answer.split())
    expected = max_marks * 25
    return min(words / expected, 1.0)


def enforce_floor(answer: str, score: float) -> float:
    if len(answer.strip().split()) < 5:
        return 0.0
    return score


def _has_code_signals(parts: list[QuestionPart]) -> bool:
    return any(p.part_type == PartType.CODE for p in parts)


def split_answer_by_parts(answer: str, parts: list[QuestionPart]) -> list[str]:
    marker_split = re.split(r"\n\s*(?:[a-d]\)|Q?\d+\.)\s*", answer)
    marker_split = [s.strip() for s in marker_split if s.strip()]
    if len(marker_split) == len(parts):
        return marker_split

    words       = answer.split()
    total_marks = sum(p.marks for p in parts)
    result      = []
    start       = 0
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            result.append(" ".join(words[start:]))
        else:
            weight = (part.marks / total_marks) if total_marks > 0 else (1 / len(parts))
            count  = max(1, int(len(words) * weight))
            result.append(" ".join(words[start:start + count]))
            start += count
    return result


def flag_to_message(flag: str, part_index: int) -> str:
    label = f"Part {chr(65 + part_index)}"
    messages = {
        "too_short":                  f"{label}: Answer is too brief for the marks allocated.",
        "low_keyword_coverage":       f"{label}: Key domain terms from the question are missing.",
        "low_conceptual_similarity":  f"{label}: Answer may not be addressing the question directly.",
        "contradiction_detected":     f"{label}: Part of the answer may contradict the correct concept.",
        "code_too_short":             f"{label}: Code answer is very short — include the full program.",
        "diagram_extracted":          f"{label}: Diagram text was extracted and included in scoring.",
    }
    if flag.startswith("missing_constructs:"):
        constructs = flag.split(":")[1]
        return f"{label}: Code may be missing: {constructs}."
    if flag.startswith("syntax_error:"):
        lang = flag.split(":")[1]
        return f"{label}: Code has syntax errors ({lang.upper()})."
    if flag.startswith("no_syntax_checker:"):
        lang = flag.split(":")[1]
        return f"{label}: Syntax check unavailable for {lang.upper()} — scored on construct coverage."
    return messages.get(flag, f"{label}: {flag}")


# ── Theory + Diagram scorer ────────────────────────────────────────────────────

def score_theory_part(
    part:               QuestionPart,
    student_answer:     str,
    all_question_texts: list[str],
    question_index:     int,
    index:              ReferenceIndex | None,
    has_reference:      bool,
    has_code_parts:     bool = False,
    diagram_bytes:      bytes | None = None,
) -> PartScore:
    flags = []

    # Phase 8: extract diagram text and merge with typed answer
    if diagram_bytes:
        diagram_result = extract_diagram_text(diagram_bytes)
        if diagram_result.success and diagram_result.extracted_text:
            student_answer = merge_answer_with_diagram(student_answer, diagram_result)
            flags.append("diagram_extracted")

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

    if has_reference and rg:
        weights = WEIGHTS_WITH_RAG
    elif has_code_parts:
        weights = WEIGHTS_WITHOUT_RAG_CODE_HEAVY
    else:
        weights = WEIGHTS_WITHOUT_RAG

    raw = (
        kw.score                  * weights["keyword"] +
        sb.score                  * weights["sbert"]   +
        (rg.score if rg else 0.0) * weights["rag"]     +
        ls                        * weights["length"]
    )

    # Phase 8: NLI contradiction check
    contradiction_score = None
    reference_sentences = []
    if rg and rg.retrieved_chunks:
        reference_sentences = extract_key_sentences(" ".join(rg.retrieved_chunks[:2]))
    elif not has_reference:
        reference_sentences = extract_key_sentences(part.text)

    if reference_sentences:
        raw_before          = raw
        raw                 = contradiction_penalty(reference_sentences, student_answer, raw)
        contradiction_score = round(raw_before - raw, 4) if raw < raw_before else 0.0
        if contradiction_score and contradiction_score > 0.05:
            flags.append("contradiction_detected")

    raw = enforce_floor(student_answer, raw)

    if ls < 0.4:        flags.append("too_short")
    if kw.score < 0.3:  flags.append("low_keyword_coverage")
    if sb.score < 0.4:  flags.append("low_conceptual_similarity")

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
        contradiction_score=contradiction_score,
        missed_concepts=rg.gaps if rg else kw.missed,
        feedback_flags=flags,
    )


# ── Code scorer ────────────────────────────────────────────────────────────────

def score_code_part(part: QuestionPart, student_answer: str) -> PartScore:
    flags   = []
    result: CodeResult = score_code(
        code=student_answer,
        question_text=part.text,
    )

    ls  = length_signal(student_answer, part.marks)
    raw = result.score * 0.80 + ls * 0.20
    raw = enforce_floor(student_answer, raw)

    if ls < 0.4:
        flags.append("code_too_short")
    if not result.syntax_passed and result.syntax_available:
        flags.append(f"syntax_error:{result.language}")
    if not result.syntax_available:
        flags.append(f"no_syntax_checker:{result.language}")
    if result.constructs_missed:
        flags.append(f"missing_constructs:{','.join(result.constructs_missed)}")

    return PartScore(
        part_index=part.part_index,
        part_type=part.part_type.value,
        marks=part.marks,
        raw_score=round(raw, 4),
        final_marks=round(raw * part.marks, 1),
        keyword_score=result.score,
        sbert_score=0.0,
        rag_score=None,
        length_score=ls,
        contradiction_score=None,
        missed_concepts=result.constructs_missed,
        feedback_flags=flags,
    )


# ── Main entry point ───────────────────────────────────────────────────────────

def compute_composite(
    question_id:        int,
    question_text:      str,
    student_answer:     str,
    max_marks:          int,
    all_question_texts: list[str],
    question_index:     int,
    index:              ReferenceIndex | None,
    has_reference:      bool,
    diagram_bytes:      bytes | None = None,
) -> CompositeResult:

    split: SplitResult = split_question_into_parts(question_text, max_marks)
    parts = split.parts
    code_present = _has_code_signals(parts)

    answer_segments = (
        [student_answer]
        if len(parts) == 1
        else split_answer_by_parts(student_answer, parts)
    )

    part_scores: list[PartScore] = []

    for i, part in enumerate(parts):
        seg = answer_segments[i] if i < len(answer_segments) else ""

        if part.part_type == PartType.CODE:
            ps = score_code_part(part, seg)
        else:
            ps = score_theory_part(
                part=part,
                student_answer=seg,
                all_question_texts=all_question_texts,
                question_index=question_index,
                index=index,
                has_reference=has_reference,
                has_code_parts=code_present,
                diagram_bytes=diagram_bytes if part.part_type == PartType.DIAGRAM else None,
            )
        part_scores.append(ps)

    total_final = round(min(sum(ps.final_marks for ps in part_scores), max_marks), 1)
    percentage  = round((total_final / max_marks) * 100, 1) if max_marks > 0 else 0.0

    all_gaps     = list({g for ps in part_scores for g in ps.missed_concepts})
    all_feedback = [
        flag_to_message(flag, ps.part_index)
        for ps in part_scores
        for flag in ps.feedback_flags
    ]

    return CompositeResult(
        question_id=question_id,
        max_marks=max_marks,
        final_marks=total_final,
        percentage=percentage,
        parts=part_scores,
        overall_gaps=all_gaps,
        feedback=all_feedback,
    )