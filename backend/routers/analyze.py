from fastapi import APIRouter
from pydantic import BaseModel
from engines.composite_scorer import compute_composite, CompositeResult
from routers.reference import get_index

router = APIRouter()


class AnswerItem(BaseModel):
    question_id:   int
    question_text: str
    student_answer: str
    max_marks:     int = 10
    model_answer:  str | None = None


class SubmitPayload(BaseModel):
    answers:       list[AnswerItem]
    has_reference: bool = False


class PartScoreOut(BaseModel):
    part_index:    int
    part_type:     str
    marks:         int
    raw_score:     float
    final_marks:   float
    keyword_score: float
    sbert_score:   float
    rag_score:     float | None
    length_score:  float
    missed_concepts: list[str]
    feedback_flags:  list[str]


class QuestionResult(BaseModel):
    question_id:   int
    max_marks:     int
    final_marks:   float
    percentage:    float
    parts:         list[PartScoreOut]
    overall_gaps:  list[str]
    feedback:      list[str]


class AnalysisResponse(BaseModel):
    results:       list[QuestionResult]
    total_marks:   float
    total_possible: int
    overall_percentage: float


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(payload: SubmitPayload) -> AnalysisResponse:
    index = get_index()
    has_reference = payload.has_reference and index is not None
    all_question_texts = [item.question_text for item in payload.answers]

    results = []
    for i, item in enumerate(payload.answers):
        result: CompositeResult = compute_composite(
            question_id=item.question_id,
            question_text=item.question_text,
            student_answer=item.student_answer,
            max_marks=item.max_marks,
            all_question_texts=all_question_texts,
            question_index=i,
            index=index,
            has_reference=has_reference,
        )
        results.append(QuestionResult(
            question_id=result.question_id,
            max_marks=result.max_marks,
            final_marks=result.final_marks,
            percentage=result.percentage,
            parts=[PartScoreOut(**vars(ps)) for ps in result.parts],
            overall_gaps=result.overall_gaps,
            feedback=result.feedback,
        ))

    total_marks    = round(sum(r.final_marks for r in results), 1)
    total_possible = sum(r.max_marks for r in results)
    overall_pct    = round((total_marks / total_possible) * 100, 1) if total_possible > 0 else 0.0

    return AnalysisResponse(
        results=results,
        total_marks=total_marks,
        total_possible=total_possible,
        overall_percentage=overall_pct,
    )