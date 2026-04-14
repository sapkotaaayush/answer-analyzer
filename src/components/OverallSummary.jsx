import styles from "./OverallSummary.module.css";

export default function OverallSummary({ totalMarks, totalPossible, percentage }) {
  const grade = getGrade(percentage);

  return (
    <div className={styles.summary}>
      <div className={styles.ring}>
        <svg viewBox="0 0 100 100" className={styles.svg}>
          <circle cx="50" cy="50" r="42" className={styles.track} />
          <circle
            cx="50" cy="50" r="42"
            className={styles.fill}
            strokeDasharray={`${(percentage / 100) * 264} 264`}
            style={{ stroke: gradeColor(percentage) }}
          />
        </svg>
        <div className={styles.ringLabel}>
          <span className={styles.pct}>{percentage}%</span>
          <span className={styles.grade} style={{ color: gradeColor(percentage) }}>
            {grade}
          </span>
        </div>
      </div>

      <div className={styles.meta}>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>Total marks</span>
          <span className={styles.metaValue}>{totalMarks} / {totalPossible}</span>
        </div>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>Score</span>
          <span className={styles.metaValue}>{percentage}%</span>
        </div>
        <p className={styles.hint}>
          {percentage >= 80
            ? "Excellent conceptual coverage."
            : percentage >= 60
            ? "Good understanding — review the flagged gaps."
            : "Several key concepts need attention."}
        </p>
      </div>
    </div>
  );
}

function getGrade(pct) {
  if (pct >= 80) return "A";
  if (pct >= 65) return "B";
  if (pct >= 50) return "C";
  if (pct >= 40) return "D";
  return "F";
}

function gradeColor(pct) {
  if (pct >= 80) return "#3B6D11";
  if (pct >= 60) return "#BA7517";
  return "#A32D2D";
}