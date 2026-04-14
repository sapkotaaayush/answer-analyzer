export default function QuestionCard({
  question,
  index,
  answer,
  subAnswers,
  onAnswerChange,
  onRemove,
  onQuestionTextChange,
  disabled,
  canRemove,
}) {
  const hasAnswer = answer.trim().length > 0;
  const hasSubs = question.sub_questions?.length > 0;

  return (
    <div className={`question-card ${hasAnswer ? "answered" : ""}`}>
      <div className="question-card-header">
        <span className="question-number">Q{index + 1}</span>

        {question.manual ? (
          // Manually added question — editable text field
          <input
            className="question-text-input"
            placeholder="Type your question here..."
            value={question.text}
            onChange={(e) => onQuestionTextChange(question.id, e.target.value)}
            disabled={disabled}
          />
        ) : (
          <p className="question-text">{question.text}</p>
        )}

        <div className="question-card-actions">
          {question.marks && (
            <span className="marks-badge">{question.marks} marks</span>
          )}
          {canRemove && (
            <button
              className="btn-remove"
              onClick={onRemove}
              disabled={disabled}
              title="Remove question"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* No sub-questions — single answer textarea */}
      {!hasSubs && (
        <AnswerTextarea
          id={question.id}
          value={answer}
          onChange={onAnswerChange}
          disabled={disabled}
        />
      )}

      {/* Sub-questions — one textarea each */}
      {hasSubs && (
        <div className="sub-questions">
          {question.sub_questions.map((sq, si) => (
            <div key={sq.id} className="sub-question">
              <p className="sub-question-label">
                ({String.fromCharCode(97 + si)}) {sq.text}
              </p>
              <AnswerTextarea
                id={sq.id}
                value={subAnswers[sq.id] || ""}
                onChange={onAnswerChange}
                disabled={disabled}
                small
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AnswerTextarea({ id, value, onChange, disabled, small }) {
  return (
    <div className="textarea-wrapper">
      <textarea
        className={`answer-input ${small ? "small" : ""}`}
        placeholder="Type your answer here..."
        value={value}
        onChange={(e) => onChange(id, e.target.value)}
        disabled={disabled}
        rows={small ? 3 : 5}
      />
      <span className="char-count">{value.length} chars</span>
    </div>
  );
}