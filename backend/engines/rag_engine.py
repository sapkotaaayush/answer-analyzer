import faiss
import numpy as np
import spacy
from dataclasses import dataclass
from sklearn.feature_extraction.text import TfidfVectorizer

nlp = spacy.load("en_core_web_sm")


@dataclass
class RAGResult:
    score: float
    gaps: list[str]
    retrieved_chunks: list[str]


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 350,
    overlap: int = 60,
) -> list[str]:
    """
    Split text into overlapping word-level chunks.
    Overlap ensures concepts spanning paragraph boundaries are not lost.
    """
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 20:
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


# ── Index building ────────────────────────────────────────────────────────────

class ReferenceIndex:
    """
    Holds the FAISS index and original chunks.
    Built once on textbook upload, queried on every answer submission.
    """

    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        embeddings = embed_chunks(chunks)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

    def retrieve(self, query: str, k: int = 3) -> list[str]:
        if self.index.ntotal == 0:
            return []
        k = min(k, self.index.ntotal)
        query_vec = embed(query).reshape(1, -1).astype("float32")
        _, indices = self.index.search(query_vec, k)
        return [self.chunks[i] for i in indices[0] if i < len(self.chunks)]


def embed(text: str) -> np.ndarray:
    from engines.sbert_engine import get_model
    model = get_model()
    return model.encode(text, normalize_embeddings=True)


def embed_chunks(chunks: list[str]) -> np.ndarray:
    from engines.sbert_engine import get_model
    model = get_model()
    embeddings = model.encode(
        chunks,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.array(embeddings, dtype="float32")


# ── Term extraction ───────────────────────────────────────────────────────────

def get_important_terms(
    target_chunks: list[str],
    all_chunks: list[str],
    top_n: int = 15,
) -> set[str]:
    """
    Use TF-IDF across the full index to find terms that are distinctive
    to the retrieved chunks vs the rest of the material.

    Terms appearing everywhere in the textbook score near zero — subject-agnostic
    noise filtering with no hardcoded word lists.

    max_df=0.7 means any term in more than 70% of all chunks is treated as
    background noise regardless of subject. Works for Java, biology, graphics,
    any domain automatically.

    ngram_range=(1, 2) captures both single terms ("stub") and two-word phrases
    ("transport layer", "remote object") for richer gap detection.
    """
    if not all_chunks or not target_chunks:
        return set()

    target_doc = " ".join(target_chunks)
    corpus = [target_doc] + all_chunks

    try:
        vectorizer = TfidfVectorizer(
            min_df=1,
            max_df=0.7,
            ngram_range=(1, 2),
            stop_words="english",
            token_pattern=r"[a-zA-Z][a-zA-Z0-9\-]{2,}",
        )
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return set()

    feature_names = vectorizer.get_feature_names_out()
    target_scores = matrix[0].toarray().flatten()

    ranked = sorted(
        zip(feature_names, target_scores),
        key=lambda x: x[1],
        reverse=True,
    )

    return {term for term, score in ranked[:top_n] if score > 0}


def extract_answer_terms(text: str) -> set[str]:
    """
    Extract terms from a student answer.
    Uses the same broad extraction so matching against required terms is fair.
    No stopword filtering beyond spaCy defaults — we want to catch
    everything the student actually wrote.
    """
    doc = nlp(text.lower())

    chunks = {
        chunk.lemma_.strip()
        for chunk in doc.noun_chunks
        if len(chunk.lemma_.strip()) > 2
    }

    entities = {
        ent.lemma_.lower()
        for ent in doc.ents
        if len(ent.lemma_) > 2
    }

    tokens = {
        token.lemma_
        for token in doc
        if not token.is_stop
        and not token.is_punct
        and token.pos_ in ("NOUN", "PROPN")
        and len(token.lemma_) > 3
    }

    return chunks | entities | tokens


# ── Scoring ───────────────────────────────────────────────────────────────────

def rag_score(
    question_text: str,
    student_answer: str,
    index: ReferenceIndex,
    k: int = 3,
) -> RAGResult:
    """
    Score a student answer against retrieved reference chunks.

    Retrieval uses the question as the query so the chunks are topically
    relevant to what was asked, not just what the student happened to write.

    Matching uses partial overlap — "transport layer" in required terms matches
    if the student writes "transport" anywhere in their answer. This prevents
    penalizing students who understand the concept but paraphrase it slightly.

    Args:
        question_text:  Query for FAISS retrieval.
        student_answer: The student's answer text.
        index:          Pre-built ReferenceIndex from uploaded textbook.
        k:              Chunks to retrieve. Use 3 for specific questions,
                        5 for broad architecture/overview questions.

    Returns:
        RAGResult with score (0–1), gap list, and retrieved chunks.
    """
    if not student_answer.strip():
        return RAGResult(score=0.0, gaps=[], retrieved_chunks=[])

    retrieved = index.retrieve(question_text, k=k)

    if not retrieved:
        return RAGResult(score=0.5, gaps=[], retrieved_chunks=[])

    required_terms = get_important_terms(
        target_chunks=retrieved,
        all_chunks=index.chunks,
        top_n=15,
    )

    if not required_terms:
        return RAGResult(score=0.5, gaps=[], retrieved_chunks=retrieved)

    answer_terms = extract_answer_terms(student_answer)
    answer_words = set(" ".join(answer_terms).split())

    matched = set()
    missed = set()

    for req_term in required_terms:
        req_words = set(req_term.split())
        # Partial match — any significant word from the required term
        # found anywhere in the answer counts as covered
        if req_words & answer_words:
            matched.add(req_term)
        else:
            missed.add(req_term)

    score = round(len(matched) / len(required_terms), 4)

    return RAGResult(
        score=score,
        gaps=sorted(missed),
        retrieved_chunks=retrieved,
    )