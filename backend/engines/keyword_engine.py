import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from dataclasses import dataclass

nlp = spacy.load("en_core_web_sm")

QUESTION_STOPWORDS = {
    "what", "explain", "describe", "list", "define", "use", "role",
    "way", "example", "detail", "note", "type", "advantage",
    "difference", "feature", "provide", "give", "write", "create",
    "short", "proper", "different", "following", "two", "any",
}

GENERIC_TOKENS = QUESTION_STOPWORDS | {
    "java", "program", "application", "class", "object",
    "method", "interface", "value", "number", "result",
    "user", "system", "data", "information", "process",
}

# Determiners, pronouns, and particles that should never appear in a keyword
CHUNK_NOISE_STARTS = {
    "the", "a", "an", "this", "that", "these", "those",
    "which", "what", "how", "its", "their", "our", "your",
    "some", "any", "all", "each", "every", "both",
}

# Single words that are meaningless as standalone concepts
SINGLE_WORD_BLACKLIST = {
    "which", "that", "this", "those", "these", "it", "them",
    "they", "we", "he", "she", "when", "where", "why", "how",
    "also", "then", "now", "just", "only", "very", "more",
    "column", "record", "table", "row", "item", "field",
    "thing", "part", "name", "date", "time", "year",
}


def _is_meaningful_chunk(lemma: str) -> bool:
    """
    Return True only if a noun chunk lemma is worth keeping as a required term.
    Rejects: starts with a determiner/pronoun, all-stopword phrases,
             single blacklisted words, very short tokens.
    """
    if not lemma or len(lemma.strip()) < 3:
        return False

    words = lemma.strip().lower().split()

    # Starts with a noise determiner/pronoun
    if words[0] in CHUNK_NOISE_STARTS:
        return False

    # Every word is a stopword / noise word
    if all(w in (CHUNK_NOISE_STARTS | QUESTION_STOPWORDS | GENERIC_TOKENS) for w in words):
        return False

    # Single word that is in the blacklist
    if len(words) == 1 and words[0] in SINGLE_WORD_BLACKLIST:
        return False

    return True


def extract_keywords(text: str) -> set[str]:
    doc = nlp(text.lower())

    chunks = {
        chunk.lemma_.strip()
        for chunk in doc.noun_chunks
        if _is_meaningful_chunk(chunk.lemma_.strip())
        and chunk.lemma_.strip() not in QUESTION_STOPWORDS
    }

    entities = {
        ent.lemma_.lower()
        for ent in doc.ents
        if len(ent.lemma_) > 2
        and ent.lemma_.lower() not in SINGLE_WORD_BLACKLIST
    }

    tokens = {
        token.lemma_
        for token in doc
        if not token.is_stop
        and not token.is_punct
        and token.pos_ in ("NOUN", "PROPN")
        and len(token.lemma_) > 3
        and token.lemma_ not in GENERIC_TOKENS
        and token.lemma_ not in SINGLE_WORD_BLACKLIST
    }

    return chunks | entities | tokens


def _tfidf_filter(
    keyword_sets: list[set[str]],
    target_index: int,
    top_n: int = 8,
) -> set[str]:
    if len(keyword_sets) < 2:
        return keyword_sets[target_index]

    docs = [" ".join(kws) for kws in keyword_sets]
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(docs)
    feature_names = vectorizer.get_feature_names_out()
    scores = matrix[target_index].toarray().flatten()

    ranked = sorted(
        zip(feature_names, scores),
        key=lambda x: x[1],
        reverse=True,
    )

    top_terms = {term for term, score in ranked[:top_n] if score > 0}
    return keyword_sets[target_index] | top_terms


@dataclass
class KeywordResult:
    score: float
    matched: list[str]
    missed: list[str]
    total_required: int


def keyword_score(
    question_text: str,
    student_answer: str,
    all_question_texts: list[str] | None = None,
    question_index: int = 0,
) -> KeywordResult:
    if not student_answer.strip():
        return KeywordResult(score=0.0, matched=[], missed=[], total_required=0)

    all_kw_sets = (
        [extract_keywords(q) for q in all_question_texts]
        if all_question_texts
        else [extract_keywords(question_text)]
    )

    required = (
        _tfidf_filter(all_kw_sets, question_index)
        if all_question_texts
        else all_kw_sets[0]
    )

    # Final guard: remove any required term that slipped through and is noise
    required = {t for t in required if _is_meaningful_chunk(t)}

    if not required:
        return KeywordResult(score=0.5, matched=[], missed=[], total_required=0)

    present = extract_keywords(student_answer)
    matched = sorted(required & present)
    missed  = sorted(required - present)

    return KeywordResult(
        score=round(len(matched) / len(required), 4),
        matched=matched,
        missed=missed,
        total_required=len(required),
    )