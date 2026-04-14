export default function SubmitBar({ answeredCount, totalCount, onSubmit, isSubmitting }) {
  const allAnswered = answeredCount === totalCount && totalCount > 0;
  const pct = totalCount > 0 ? (answeredCount / totalCount) * 100 : 0;

  return (
    <div className="submit-bar">
      <div className="submit-bar-progress">
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${pct}%` }} />
        </div>
        <span className="progress-label">
          {answeredCount} of {totalCount} answered
        </span>
      </div>

      <button
        className={`btn-submit ${allAnswered ? "ready" : ""}`}
        onClick={onSubmit}
        disabled={isSubmitting || totalCount === 0}
      >
        {isSubmitting ? (
          <>
            <span className="btn-spinner" />
            Analyzing...
          </>
        ) : (
          "Submit for Analysis"
        )}
      </button>
    </div>
  );
}