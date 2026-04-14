from sentence_transformers import CrossEncoder
from dataclasses import dataclass

# Loads once at startup — ~85MB model
_nli_model: CrossEncoder | None = None


def get_nli_model() -> CrossEncoder:
    global _nli_model
    if _nli_model is None:
        _nli_model = CrossEncoder("cross-encoder/nli-deberta-v3-small")
    return _nli_model


@dataclass
class NLIResult:
    contradiction_score: float   # 0.0 – 1.0
    entailment_score:    float   # 0.0 – 1.0
    is_contradicting:    bool


def check_contradiction(
    reference: str,
    student_answer: str,
    threshold: float = 0.65,
) -> NLIResult:
    """
    Check whether a student answer contradicts a reference statement.

    The NLI model classifies a sentence pair as one of:
        0 = contradiction
        1 = entailment
        2 = neutral

    We use the contradiction probability to penalize answers that
    actively state the opposite of the correct concept — something
    SBERT cosine similarity cannot detect because it only measures
    closeness, not direction.

    Args:
        reference:      A reference sentence (model answer sentence or
                        a sentence from a RAG-retrieved chunk).
        student_answer: The student's answer text.
        threshold:      Contradiction probability above which we flag.

    Returns:
        NLIResult with scores and is_contradicting flag.
    """
    if not reference.strip() or not student_answer.strip():
        return NLIResult(
            contradiction_score=0.0,
            entailment_score=0.0,
            is_contradicting=False,
        )

    model  = get_nli_model()
    scores = model.predict(
        [(reference, student_answer)],
        apply_softmax=True,
    )[0]

    # scores = [contradiction, entailment, neutral]
    contradiction = float(scores[0])
    entailment    = float(scores[1])

    return NLIResult(
        contradiction_score=round(contradiction, 4),
        entailment_score=round(entailment, 4),
        is_contradicting=contradiction > threshold,
    )


def contradiction_penalty(
    reference_sentences: list[str],
    student_answer: str,
    base_score: float,
) -> float:
    """
    Apply a penalty to a base score if the student answer contradicts
    any of the reference sentences.

    Penalty is proportional to the contradiction score so a mild
    contradiction causes a small deduction, a strong contradiction
    causes a larger one.

    Args:
        reference_sentences: Key sentences from model answer or RAG chunks.
        student_answer:      Student's full answer text.
        base_score:          The score before contradiction check (0–1).

    Returns:
        Adjusted score (always >= 0).
    """
    if not reference_sentences:
        return base_score

    max_contradiction = 0.0
    for ref_sentence in reference_sentences:
        result = check_contradiction(ref_sentence, student_answer)
        if result.contradiction_score > max_contradiction:
            max_contradiction = result.contradiction_score

    if max_contradiction < 0.5:
        return base_score

    # Penalty scales from 0 (at threshold 0.5) to 0.3 (at score 1.0)
    penalty = (max_contradiction - 0.5) * 0.6
    return round(max(0.0, base_score - penalty), 4)


def extract_key_sentences(text: str, max_sentences: int = 3) -> list[str]:
    """
    Extract the most informative sentences from a reference text
    to use as contradiction check targets.
    Skips very short sentences and headers.
    """
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    key = [
        s.strip()
        for s in sentences
        if len(s.strip().split()) >= 8
    ]
    return key[:max_sentences]
