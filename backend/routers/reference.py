import tempfile
import os
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import pdfplumber
from engines.rag_engine import chunk_text, ReferenceIndex

router = APIRouter()

# In-memory store — one index per session
# Phase 8 can add persistence if needed
_reference_index: ReferenceIndex | None = None


def get_index() -> ReferenceIndex | None:
    return _reference_index


def extract_text(pdf_path: str) -> str:
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                lines.append(text.strip())
    return "\n".join(lines)


def is_text_pdf(pdf_path: str) -> bool:
    with pdfplumber.open(pdf_path) as pdf:
        sample = pdf.pages[0].extract_text()
        return sample is not None and len(sample.strip()) > 100


@router.post("/upload-reference")
async def upload_reference(file: UploadFile = File(...)):
    global _reference_index

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

        raw_text = extract_text(tmp_path)
        chunks = chunk_text(raw_text)

        if not chunks:
            return JSONResponse(
                status_code=422,
                content={"error": "Could not extract text from this PDF."}
            )

        # Build FAISS index — this is the one-time cost on upload
        _reference_index = ReferenceIndex(chunks)

        return {
            "message": "Reference material indexed successfully.",
            "chunks_indexed": len(chunks),
        }

    finally:
        os.unlink(tmp_path)


@router.delete("/upload-reference")
async def clear_reference():
    global _reference_index
    _reference_index = None
    return {"message": "Reference material cleared."}