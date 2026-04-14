import re
import tempfile
import os
from dataclasses import dataclass, field
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import pdfplumber

router = APIRouter()

# ── PDF validation ─────────────────────────────────────────────────────────────

def is_text_pdf(pdf_path: str) -> bool:
    with pdfplumber.open(pdf_path) as pdf:
        sample = pdf.pages[0].extract_text()
        return sample is not None and len(sample.strip()) > 100

# ── Text extraction ─────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> str:
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                lines.append(text.strip())
    return "\n".join(lines)

# ── Lines to skip entirely ──────────────────────────────────────────────────────

SKIP_PATTERNS = re.compile(
    r"""
    ^\s*(
        Group\s+[A-Z]                        # Group B, Group C
      | Attempt\s+any                        # Attempt any SIX questions
      | Full\s+Marks                         # Full Marks: 40
      | Pass\s+Marks                         # Pass Marks: 24
      | Time:                                # Time: 3 hours
      | Candidates\s+are                     # Candidates are required...
      | Tribhuvan                            # University header
      | Faculty\s+of                         # Faculty of...
      | Subject:                             # Subject: ...
      | Bachelor                             # Bachelor in...
      | Course\s+Title                       # Course Title:
      | Semester:                            # Semester: VI
      | \d{4}\s+Batch                        # 2019 Batch
      | \[.*\]                               # [6x5 = 30] marks lines
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ── Question start: line begins with a number + period ─────────────────────────
# Matches: "2. What", "9. How", "10. Explain"
# Does NOT match: "a)", "b)", "(1)" inside question bodies

QUESTION_START = re.compile(r"^\s*(\d{1,2})\.\s+\S")

# ── Marks at end of line ────────────────────────────────────────────────────────

MARKS_PATTERN = re.compile(
    r"[\[\(]?\s*(\d+)\s*(?:marks?|pts?|m)\s*[\]\)]?\s*$",
    re.IGNORECASE,
)

# ── Sub-question: a), b), c) at line start ─────────────────────────────────────

SUB_QUESTION = re.compile(r"^\s*([a-z])\)\s+(.+)$", re.IGNORECASE)

# ── Data classes ────────────────────────────────────────────────────────────────

@dataclass
class SubQuestion:
    id: str
    text: str

@dataclass
class Question:
    id: int
    number: int          # original number from paper (2, 3, 4...)
    text: str
    marks: int | None = None
    sub_questions: list = field(default_factory=list)

# ── Core extraction ─────────────────────────────────────────────────────────────

def extract_questions(raw_text: str) -> list[Question]:
    lines = raw_text.split("\n")
    questions: list[Question] = []
    current_lines: list[str] = []
    current_number: int | None = None
    sequential_id = [0]

    def flush() -> None:
        nonlocal current_number
        if not current_lines or current_number is None:
            return

        # Separate sub-questions from main text
        main_parts: list[str] = []
        subs: list[SubQuestion] = []

        for line in current_lines:
            sub_match = SUB_QUESTION.match(line)
            if sub_match:
                letter = sub_match.group(1).lower()
                sub_text = sub_match.group(2).strip()
                subs.append(SubQuestion(id=f"sub_{letter}", text=sub_text))
            else:
                main_parts.append(line.strip())

        main_text = " ".join(p for p in main_parts if p)

        # Extract marks if present
        marks = None
        m = MARKS_PATTERN.search(main_text)
        if m:
            marks = int(m.group(1))
            main_text = main_text[: m.start()].strip()

        if not main_text:
            return

        sequential_id[0] += 1
        questions.append(
            Question(
                id=sequential_id[0],
                number=current_number,
                text=main_text,
                marks=marks,
                sub_questions=subs,
            )
        )
        current_lines.clear()
        current_number = None

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and header/footer lines
        if not stripped or SKIP_PATTERNS.match(stripped):
            continue

        q_match = QUESTION_START.match(stripped)
        if q_match:
            flush()
            current_number = int(q_match.group(1))
            # Strip the leading "2. " prefix before storing
            text_part = re.sub(r"^\s*\d{1,2}\.\s+", "", stripped)
            current_lines.append(text_part)
        else:
            if current_number is not None:
                current_lines.append(stripped)

    flush()  # last question
    return questions


def parse_question_paper(pdf_path: str) -> list[dict]:
    raw_text = extract_text(pdf_path)
    questions = extract_questions(raw_text)

    return [
        {
            "id": q.id,
            "number": q.number,
            "text": q.text,
            "marks": q.marks,
            "sub_questions": [
                {"id": s.id, "text": s.text}
                for s in q.sub_questions
            ],
        }
        for q in questions
    ]


# ── Endpoint ────────────────────────────────────────────────────────────────────

@router.post("/parse-paper")
async def parse_paper(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"error": "Only PDF files are supported."}
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        if not is_text_pdf(tmp_path):
            return JSONResponse(
                status_code=422,
                content={"error": "Scanned PDF detected. Please upload a text-based PDF."}
            )
        questions = parse_question_paper(tmp_path)
        return {"questions": questions, "count": len(questions)}
    finally:
        os.unlink(tmp_path)