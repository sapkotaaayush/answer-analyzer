import base64
import requests
from dataclasses import dataclass


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"


@dataclass
class DiagramResult:
    extracted_text: str      # text extracted from the diagram image
    success:        bool
    error:          str | None


def is_ollama_available() -> bool:
    """Check if the local Ollama server is running."""
    try:
        res = requests.get("http://localhost:11434", timeout=2)
        return res.status_code == 200
    except Exception:
        return False


def extract_diagram_text(image_bytes: bytes) -> DiagramResult:
    """
    Send a diagram image to LLaVA (via local Ollama) and extract
    all visible text labels, arrows, relationships, and structure.

    The extracted text is treated as additional answer content and
    fed into the same keyword + SBERT + RAG pipeline as typed text.

    Setup required (one-time):
        1. Install Ollama: https://ollama.ai
        2. Pull LLaVA:  ollama pull llava
        3. Ollama runs automatically as a background service

    Args:
        image_bytes: Raw bytes of the diagram image (JPEG or PNG).

    Returns:
        DiagramResult with extracted text or error message.
    """
    if not is_ollama_available():
        return DiagramResult(
            extracted_text="",
            success=False,
            error="Ollama is not running. Start it with: ollama serve",
        )

    try:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "This image shows a diagram from a university exam answer. "
            "Extract ALL visible text labels, box titles, arrow labels, "
            "and relationships shown in the diagram. "
            "Describe the connections between components. "
            "Output plain text only — no markdown, no bullet points. "
            "If there is no meaningful text in the diagram, output: NO_TEXT"
        )

        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        extracted = response.json().get("response", "").strip()

        if not extracted or extracted == "NO_TEXT":
            return DiagramResult(
                extracted_text="",
                success=True,
                error=None,
            )

        return DiagramResult(
            extracted_text=extracted,
            success=True,
            error=None,
        )

    except requests.exceptions.Timeout:
        return DiagramResult(
            extracted_text="",
            success=False,
            error="LLaVA timed out processing the diagram.",
        )
    except Exception as e:
        return DiagramResult(
            extracted_text="",
            success=False,
            error=str(e),
        )


def merge_answer_with_diagram(
    typed_answer: str,
    diagram_result: DiagramResult,
) -> str:
    """
    Combine the student's typed answer with text extracted from
    their diagram. The merged text goes into all scoring engines.
    """
    if not diagram_result.success or not diagram_result.extracted_text:
        return typed_answer

    return f"{typed_answer} {diagram_result.extracted_text}".strip()
