import QuestionCard from "./QuestionCard";

export default function QuestionList({
  questions,
  answers,
  onAnswerChange,
  onAddQuestion,
  onRemoveQuestion,
  onQuestionTextChange,
  disabled,
}) {
  return (
    <div className="question-list">
      <div className="question-list-header">
        <h2>{questions.length} question{questions.length !== 1 ? "s" : ""} detected</h2>
        <button
          className="btn-add"
          onClick={onAddQuestion}
          disabled={disabled}
        >
          + Add question
        </button>
      </div>

      {questions.map((q, index) => (
        <QuestionCard
          key={q.id}
          question={q}
          index={index}
          answer={answers[q.id] || ""}
          subAnswers={Object.fromEntries(
            (q.sub_questions || []).map((sq) => [sq.id, answers[sq.id] || ""])
          )}
          onAnswerChange={onAnswerChange}
          onRemove={() => onRemoveQuestion(q.id)}
          onQuestionTextChange={onQuestionTextChange}
          disabled={disabled}
          canRemove={questions.length > 1}
        />
      ))}

      <button
        className="btn-add-bottom"
        onClick={onAddQuestion}
        disabled={disabled}
      >
        + Add another question
      </button>
    </div>
  );
}