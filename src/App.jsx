import { useState } from "react";
import UploadZone from "./components/UploadZone";
import QuestionList from "./components/QuestionList";
import SubmitBar from "./components/SubmitBar";
import ReferenceUpload from "./components/ReferenceUpload";
import ResultsScreen from "./components/ResultsScreen";
import "./App.css";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [stage, setStage] = useState("upload");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState(null);
  const [hasReference, setHasReference] = useState(false);
  const [results, setResults] = useState(null);

  async function handleUpload(file) {
    setError(null);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/parse-paper`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.error) {
        setError(data.error);
        return;
      }

      const initialAnswers = {};
      data.questions.forEach((q) => {
        initialAnswers[q.id] = "";
        q.sub_questions?.forEach((sq) => {
          initialAnswers[sq.id] = "";
        });
      });

      setQuestions(data.questions);
      setAnswers(initialAnswers);
      setStage("answering");
    } catch {
      setError("Could not connect to the server. Make sure the backend is running.");
    }
  }

  function handleAnswerChange(id, value) {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }

  function handleAddQuestion() {
    const newId = Date.now();
    setQuestions((prev) => [
      ...prev,
      { id: newId, text: "", marks: null, sub_questions: [], manual: true },
    ]);
    setAnswers((prev) => ({ ...prev, [newId]: "" }));
  }

  function handleRemoveQuestion(id) {
    const q = questions.find((q) => q.id === id);
    setQuestions((prev) => prev.filter((q) => q.id !== id));
    setAnswers((prev) => {
      const copy = { ...prev };
      delete copy[id];
      q?.sub_questions?.forEach((sq) => delete copy[sq.id]);
      return copy;
    });
  }

  function handleQuestionTextChange(id, value) {
    setQuestions((prev) =>
      prev.map((q) => (q.id === id ? { ...q, text: value } : q))
    );
  }

  async function handleSubmit() {
    setStage("submitting");

    const payload = {
      answers: questions.map((q) => ({
        question_id: q.id,
        question_text: q.text,
        student_answer: answers[q.id] ?? "",
        max_marks: q.marks ?? 10,
      })),
      has_reference: hasReference,
    };

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setResults(data);
      setStage("results");
    } catch {
      setError("Submission failed. Please try again.");
      setStage("answering");
    }
  }

  function handleRetry() {
    setStage("upload");
    setQuestions([]);
    setAnswers({});
    setResults(null);
    setError(null);
    setHasReference(false);
  }

  const answeredCount = questions.filter((q) => {
    if (q.sub_questions?.length > 0) {
      return q.sub_questions.some((sq) => (answers[sq.id] ?? "").trim().length > 0);
    }
    return (answers[q.id] ?? "").trim().length > 0;
  }).length;

  const totalCount = questions.length;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Answer Analyzer</h1>
        {stage !== "upload" && stage !== "results" && (
          <span className="progress-pill">
            {answeredCount} / {totalCount} answered
          </span>
        )}
      </header>

      {(stage === "answering" || stage === "submitting") && (
        <ReferenceUpload onStatusChange={setHasReference} />
      )}

      <main className="app-main">
        {error && (
          <div className="error-banner">
            <span>{error}</span>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {stage === "upload" && (
          <UploadZone onUpload={handleUpload} />
        )}

        {(stage === "answering" || stage === "submitting") && (
          <>
            <QuestionList
              questions={questions}
              answers={answers}
              onAnswerChange={handleAnswerChange}
              onAddQuestion={handleAddQuestion}
              onRemoveQuestion={handleRemoveQuestion}
              onQuestionTextChange={handleQuestionTextChange}
              disabled={stage === "submitting"}
            />
            <SubmitBar
              answeredCount={answeredCount}
              totalCount={totalCount}
              onSubmit={handleSubmit}
              isSubmitting={stage === "submitting"}
            />
          </>
        )}

        {stage === "results" && results && (
          <ResultsScreen
            data={results}
            questions={questions}
            onRetry={handleRetry}
          />
        )}
      </main>
    </div>
  );
}