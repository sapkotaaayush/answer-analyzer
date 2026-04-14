from sentence_transformers import SentenceTransformer
import numpy as np
from dataclasses import dataclass

# Loads once at startup — not on every request
# 80MB model, cached after first download
_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


@dataclass
class SBERTResult:
    score: float        # 0.0 – 1.0 cosine similarity
    confidence: str     # "high" | "medium" | "low" — useful for frontend later


def embed(text: str) -> np.ndarray:
    return get_model().encode(text, normalize_embeddings=True)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    # Vectors are already normalized so dot product = cosine similarity
    return float(np.dot(vec_a, vec_b))


def generate_reference_answer(question_text: str) -> str:
    """
    Fallback when no model answer is available.
    Builds a minimal reference by expanding the question itself.
    Not as accurate as a real model answer but gives SBERT
    something meaningful to compare against.
    """
    # Strip question words to get the core topic
    import re
    cleaned = re.sub(
        r"^(what is|what are|explain|describe|list|define|"
        r"differentiate|compare|how|why|when|write)\s+",
        "",
        question_text.lower().strip(),
        flags=re.IGNORECASE,
    )
    # Return the core topic as a minimal reference phrase
    # e.g. "RMI architecture in Java in detail" → used as reference
    return cleaned


def sbert_score(
    question_text: str,
    student_answer: str,
    model_answer: str | None = None,
) -> SBERTResult:
    """
    Score a student answer using semantic similarity.

    Args:
        question_text:  The question being answered.
        student_answer: The student's answer text.
        model_answer:   Optional reference answer. If None, a reference
                        is derived from the question text itself.

    Returns:
        SBERTResult with score (0–1) and confidence level.
    """
    if not student_answer.strip():
        return SBERTResult(score=0.0, confidence="low")

    reference = model_answer if model_answer else generate_reference_answer(question_text)

    if not reference.strip():
        return SBERTResult(score=0.5, confidence="low")

    vec_reference = embed(reference)
    vec_student   = embed(student_answer)

    raw_score = cosine_similarity(vec_reference, vec_student)

    # Cosine similarity on academic text typically ranges 0.3–0.95
    # Normalize to 0–1 using a realistic floor of 0.2
    floor = 0.2
    normalized = max(0.0, (raw_score - floor) / (1.0 - floor))
    normalized = round(min(normalized, 1.0), 4)

    # Confidence is based on whether we have a real model answer
    if model_answer:
        confidence = "high" if normalized > 0.6 else "medium" if normalized > 0.3 else "low"
    else:
        # Without a real model answer, cap confidence
        confidence = "medium" if normalized > 0.5 else "low"

    return SBERTResult(score=normalized, confidence=confidence)