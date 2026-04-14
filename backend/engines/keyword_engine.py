import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from dataclasses import dataclass

nlp = spacy.load("en_core_web_sm")

QUESTION_STOPWORDS = {
    "what", "explain", "describe", "list", "define", "use", "role",
    "way", "example", "detail", "note", "type", "advantage",
    "difference", "feature", "provide", "give", "write", "create",
    "short", "proper", "different", "following", "two", "any"
}

GENERIC_TOKENS = QUESTION_STOPWORDS | {
    "java", "program", "application", "class", "object",
    "method", "interface", "value", "number", "result",
    "user", "system", "data", "information", "process"
}


@dataclass
class KeywordResult:
    score: float
    matched: list[str]
    missed: list[str]
    total_required: int


def extract_keywords(text: str) -> set[str]:
    doc = nlp(text.lower())

    chunks = {
        chunk.lemma_.strip()
        for chunk in doc.noun_chunks
        if len(chunk.lemma_.strip()) > 2
        and chunk.lemma_.strip() not in QUESTION_STOPWORDS
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
        and token.lemma_ not in GENERIC_TOKENS
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