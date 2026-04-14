import styles from "./ResultCard.module.css";

const TYPE_LABEL = { theory: "Theory", code: "Code", diagram: "Diagram" };
const TYPE_COLOR = {
  theory:  { bg: "#E6F1FB", text: "#0C447C" },
  code:    { bg: "#EEEDFE", text: "#3C3489" },
  diagram: { bg: "#E1F5EE", text: "#085041" },
};

// Words that should never appear as a standalone "concept to review"
const GAP_NOISE = new Set([
  "which", "that", "this", "those", "these", "it", "them", "they",
  "when", "where", "why", "how", "also", "then", "now", "just",
  "column", "record", "table", "row", "item", "field", "date",
  "name", "value", "type", "part", "thing", "number", "result",
  "the", "a", "an", "and", "or", "of", "in", "on", "at", "to",
  "with", "from", "for", "by", "is", "are", "was", "be",
]);

// Articles/determiners/pronouns that make a multi-word phrase meaningless
const NOISE_STARTS = new Set([
  "the", "a", "an", "this", "that", "these", "those",
  "which", "what", "how", "its", "their", "our", "your",
  "some", "any", "all", "each", "every", "both",
]);

function isMeaningfulGap(gap) {
  if (!gap || gap.trim().length < 3) return false;
  const words = gap.trim().toLowerCase().split(/\s+/);
  // Single-word noise
  if (words.length === 1 && GAP_NOISE.has(words[0])) return false;
  // Starts with a determiner/pronoun
  if (NOISE_STARTS.has(words[0])) return false;
  // Every word is noise
  if (words.every(w => GAP_NOISE.has(w) || NOISE_STARTS.has(w))) return false;
  return true;
}

export default function ResultCard({ result, questionText, index }) {
  const pct      = result.percentage;
  const barColor = pct >= 70 ? "#639922" : pct >= 45 ? "#BA7517" : "#A32D2D";

  const meaningfulGaps = (result.overall_gaps ?? []).filter(isMeaningfulGap);

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.header}>
        <span className={styles.qNum}>Q{index + 1}</span>
        <p className={styles.qText}>{questionText}</p>
        <div className={styles.score}>
          <span className={styles.marks}>{result.final_marks}</span>
          <span className={styles.maxMarks}>/{result.max_marks}</span>
        </div>
      </div>

      {/* Score bar */}
      <div className={styles.barTrack}>
        <div
          className={styles.barFill}
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>

      {/* Per-part breakdown */}
      {result.parts.length > 1 && (
        <div className={styles.parts}>
          {result.parts.map((part, i) => {
            const typeStyle = TYPE_COLOR[part.part_type] ?? TYPE_COLOR.theory;
            return (
              <div key={i} className={styles.part}>
                <div className={styles.partHeader}>
                  <span
                    className={styles.typePill}
                    style={{ background: typeStyle.bg, color: typeStyle.text }}
                  >
                    {TYPE_LABEL[part.part_type] ?? part.part_type}
                  </span>
                  <span className={styles.partMarks}>
                    {part.final_marks} / {part.marks} marks
                  </span>
                </div>

                <div className={styles.engines}>
                  <EngineBar label="Keywords" value={part.keyword_score} />
                  <EngineBar label="Concepts"  value={part.sbert_score} />
                  {part.rag_score !== null && (
                    <EngineBar label="Coverage" value={part.rag_score} />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Single part engine scores */}
      {result.parts.length === 1 && (
        <div className={styles.engines}>
          <EngineBar label="Keywords" value={result.parts[0].keyword_score} />
          <EngineBar label="Concepts"  value={result.parts[0].sbert_score} />
          {result.parts[0].rag_score !== null && (
            <EngineBar label="Coverage" value={result.parts[0].rag_score} />
          )}
        </div>
      )}

      {/* Gaps — only shown when there are meaningful ones */}
      {meaningfulGaps.length > 0 && (
        <div className={styles.gaps}>
          <p className={styles.gapsLabel}>Concepts to review</p>
          <div className={styles.gapTags}>
            {meaningfulGaps.map((gap, i) => (
              <span key={i} className={styles.gapTag}>{gap}</span>
            ))}
          </div>
        </div>
      )}

      {/* Feedback */}
      {result.feedback.length > 0 && (
        <div className={styles.feedback}>
          {result.feedback.map((line, i) => (
            <p key={i} className={styles.feedbackLine}>↳ {line}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function EngineBar({ label, value }) {
  const pct   = Math.round((value ?? 0) * 100);
  const color = pct >= 70 ? "#639922" : pct >= 45 ? "#BA7517" : "#A32D2D";
  return (
    <div className={styles.engineRow}>
      <span className={styles.engineLabel}>{label}</span>
      <div className={styles.engineTrack}>
        <div className={styles.engineFill} style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className={styles.enginePct}>{pct}%</span>
    </div>
  );
}
