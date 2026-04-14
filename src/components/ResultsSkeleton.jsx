import styles from "./ResultsSkeleton.module.css";

export default function ResultsSkeleton({ questionCount = 3 }) {
  return (
    <div className={styles.screen}>
      <div className={styles.summarySkeleton}>
        <div className={styles.ringPlaceholder} />
        <div className={styles.metaPlaceholder}>
          <div className={`${styles.line} ${styles.lineWide}`} />
          <div className={`${styles.line} ${styles.lineMid}`} />
          <div className={`${styles.line} ${styles.lineShort}`} />
        </div>
      </div>

      {Array.from({ length: questionCount }).map((_, i) => (
        <div key={i} className={styles.cardSkeleton}>
          <div className={styles.cardHeader}>
            <div className={styles.numPlaceholder} />
            <div className={`${styles.line} ${styles.lineWide}`} />
            <div className={styles.scorePlaceholder} />
          </div>
          <div className={styles.barPlaceholder} />
          <div className={styles.engineRows}>
            {["Keywords", "Concepts", "Coverage", "Length"].map((label) => (
              <div key={label} className={styles.engineRow}>
                <div className={styles.engineLabel} />
                <div className={styles.engineTrack} />
                <div className={styles.enginePct} />
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className={styles.statusLine}>
        <span className={styles.spinner} />
        <span className={styles.statusText}>Analyzing your answers...</span>
      </div>
    </div>
  );
}
