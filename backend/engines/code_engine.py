import os
import re
import subprocess
import tempfile
import py_compile
from dataclasses import dataclass


@dataclass
class CodeResult:
    score:              float         # 0.0 – 1.0
    language:           str
    syntax_passed:      bool
    syntax_available:   bool          # False if no compiler found
    constructs_matched: list[str]
    constructs_missed:  list[str]
    feedback:           list[str]


# ── Language detection ────────────────────────────────────────────────────────

def detect_language(code: str, question_text: str) -> str:
    q = question_text.lower()

    # Question-text signals are most reliable
    if any(k in q for k in ["java ", "javabeans", "servlet", "jvm", "jdbc", "rmi", "swing"]):
        return "java"
    if any(k in q for k in ["python", ".py", "django", "flask"]):
        return "python"
    if any(k in q for k in ["c#", ".net", "asp.net", "linq", "delegate", "csharp"]):
        return "csharp"
    if any(k in q for k in ["c++", "cpp", "pointer", "template", "stl"]):
        return "cpp"

    # Code content signals as fallback
    if "import java" in code or "public class" in code or "System.out" in code:
        return "java"
    if re.search(r"\bdef \w+\(", code) or "print(" in code or "import numpy" in code:
        return "python"
    if "using System" in code or "Console.Write" in code or "namespace " in code:
        return "csharp"
    if "#include" in code or "->" in code:
        return "cpp"

    return "c"  # default


# ── Syntax checkers ───────────────────────────────────────────────────────────

def check_c_syntax(code: str, lang: str = "c") -> tuple[bool, bool]:
    """
    Returns (syntax_passed, compiler_available).
    Uses gcc for C, g++ for C++.
    -fsyntax-only checks without producing a binary — safe and fast.
    """
    compiler = "gcc" if lang == "c" else "g++"
    ext      = ".c"  if lang == "c" else ".cpp"

    try:
        subprocess.run([compiler, "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, False   # compiler not found

    with tempfile.NamedTemporaryFile(suffix=ext, mode="w", delete=False) as f:
        f.write(code)
        path = f.name

    try:
        result = subprocess.run(
            [compiler, "-fsyntax-only", path],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0, True
    except subprocess.TimeoutExpired:
        return False, True
    finally:
        os.unlink(path)


def check_java_syntax(code: str) -> tuple[bool, bool]:
    """
    Uses javac to check Java syntax.
    -proc:none skips annotation processing — faster.
    Wraps bare code in a class if no class declaration found.
    """
    try:
        subprocess.run(["javac", "-version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, False

    # Wrap bare method code in a class so javac doesn't reject it
    if "public class" not in code and "class " not in code:
        code = f"public class Solution {{\n{code}\n}}"

    with tempfile.NamedTemporaryFile(suffix=".java", mode="w", delete=False, dir="/tmp") as f:
        f.write(code)
        path = f.name

    try:
        result = subprocess.run(
            ["javac", "-proc:none", path],
            capture_output=True,
            timeout=15,
        )
        return result.returncode == 0, True
    except subprocess.TimeoutExpired:
        return False, True
    finally:
        os.unlink(path)


def check_python_syntax(code: str) -> tuple[bool, bool]:
    """
    Uses Python's built-in py_compile — no external tools needed.
    Always available.
    """
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        path = f.name

    try:
        py_compile.compile(path, doraise=True)
        return True, True
    except py_compile.PyCompileError:
        return False, True
    finally:
        os.unlink(path)
        cached = path + "c"
        if os.path.exists(cached):
            os.unlink(cached)


# ── Construct checker ─────────────────────────────────────────────────────────

def check_constructs(
    code: str,
    question_text: str,
    language: str,
) -> tuple[list[str], list[str]]:
    """
    Extract required constructs from the question text and check
    whether they appear in the student's code.

    Language-specific construct patterns are added to the base check.
    Returns (matched, missed).
    """
    # Base constructs extracted from question text
    base_patterns = re.findall(
        r"\b(class|interface|method|constructor|loop|recursion|"
        r"overload|override|exception|try|catch|finally|"
        r"static|abstract|virtual|async|return|void)\b",
        question_text,
        re.IGNORECASE,
    )

    # Language-specific required patterns
    lang_patterns = {
        "java":   ["public", "class", "void", "main"],
        "python": ["def", "return"],
        "cpp":    ["#include", "int main"],
        "c":      ["#include", "int main"],
        "csharp": ["class", "static", "void"],
    }

    required = list(set(
        [p.lower() for p in base_patterns]
        + lang_patterns.get(language, [])
    ))

    code_lower = code.lower()
    matched = [c for c in required if c.lower() in code_lower]
    missed  = [c for c in required if c.lower() not in code_lower]

    return matched, missed


# ── Main scoring function ─────────────────────────────────────────────────────

def score_code(
    code: str,
    question_text: str,
) -> CodeResult:
    """
    Score a student's typed code answer.

    Layers:
        1. Language detection
        2. Syntax check (if compiler available)
        3. Construct coverage check
        4. Weighted composite

    Weights:
        syntax     0.40  (binary — compiles or doesn't)
        constructs 0.40  (partial — coverage ratio)
        Both equal 0.50 when syntax checker unavailable
    """
    feedback  = []
    language  = detect_language(code, question_text)

    # ── Syntax check ──────────────────────────────────────────────
    if language in ("c", "cpp"):
        syntax_passed, syntax_available = check_c_syntax(code, language)
    elif language == "java":
        syntax_passed, syntax_available = check_java_syntax(code)
    elif language == "python":
        syntax_passed, syntax_available = check_python_syntax(code)
    else:
        # C# and others — no syntax check
        syntax_passed, syntax_available = False, False

    # ── Construct check ───────────────────────────────────────────
    matched, missed = check_constructs(code, question_text, language)
    construct_score = len(matched) / (len(matched) + len(missed)) if (matched or missed) else 0.5

    # ── Composite ─────────────────────────────────────────────────
    if syntax_available:
        syntax_score = 1.0 if syntax_passed else 0.0
        score = syntax_score * 0.40 + construct_score * 0.40 + 0.20
        # The extra 0.20 is a baseline for submitting something
    else:
        # No compiler — rely entirely on construct coverage
        score = construct_score

    # ── Feedback ──────────────────────────────────────────────────
    if syntax_available and not syntax_passed:
        feedback.append(f"Code has syntax errors ({language.upper()}).")
    if missed:
        feedback.append(f"Code may be missing: {', '.join(missed)}.")
    if not syntax_available:
        feedback.append(f"Syntax check not available for {language.upper()} — scored on construct coverage only.")

    return CodeResult(
        score=round(min(score, 1.0), 4),
        language=language,
        syntax_passed=syntax_passed,
        syntax_available=syntax_available,
        constructs_matched=matched,
        constructs_missed=missed,
        feedback=feedback,
    )
