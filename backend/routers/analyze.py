import json
from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from engines.composite_scorer import compute_composite, CompositeResult
from routers.reference import get_index

router = APIRouter()


# ── Response models ────────────────────────────────────────────────────────────

class PartScoreOut(BaseModel):
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


class QuestionResult(BaseModel):
    question_id:  int
    max_marks:    int
    final_marks:  float
    percentage:   float
    parts:        list[PartScoreOut]
    overall_gaps: list[str]
    feedback:     list[str]


class AnalysisResponse(BaseModel):
    results:            list[QuestionResult]
    total_marks:        float
    total_possible:     int
    overall_percentage: float


# ── Endpoint ───────────────────────────────────────────────────────────────────
#
# Accepts multipart/form-data so diagram images can be sent alongside text.
#
# Form fields:
#   payload        JSON string — same shape as before:
#                  { answers: [...], has_reference: bool }
#
#   diagrams       Optional list of image files.
#                  Each file named "{question_id}.jpg" (or .png).
#                  The filename is used to map the image to the right question.

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    payload:  str           = Form(...),
    diagrams: list[UploadFile] = File(default=[]),
) -> AnalysisResponse:

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": "Invalid payload JSON."})

    answers       = data.get("answers", [])
    has_reference = data.get("has_reference", False)

    # Build diagram lookup: { question_id_str: bytes }
    diagram_map: dict[str, bytes] = {}
    for upload in diagrams:
        if upload.filename and upload.size and upload.size > 0:
            stem = upload.filename.rsplit(".", 1)[0]   # "7" from "7.jpg"
            diagram_map[stem] = await upload.read()

    index         = get_index()
    has_reference = has_reference and index is not None
    all_texts     = [item["question_text"] for item in answers]

    results = []
    for i, item in enumerate(answers):
        qid           = item["question_id"]
        diagram_bytes = diagram_map.get(str(qid))

        result: CompositeResult = compute_composite(
            question_id=qid,
            question_text=item["question_text"],
            student_answer=item.get("student_answer", ""),
            max_marks=item.get("max_marks", 10),
            all_question_texts=all_texts,
            question_index=i,
            index=index,
            has_reference=has_reference,
            diagram_bytes=diagram_bytes,
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
