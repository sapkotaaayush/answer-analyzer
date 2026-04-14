import OverallSummary from "./OverallSummary";
import ResultCard from "./ResultCard";
import styles from "./ResultsScreen.module.css";

export default function ResultsScreen({ data, questions, onRetry }) {
  return (
    <div className={styles.screen}>
      <OverallSummary
        totalMarks={data.total_marks}
        totalPossible={data.total_possible}
        percentage={data.overall_percentage}
      />

      <div className={styles.cards}>
        {data.results.map((result, i) => {
          const question = questions.find((q) => q.id === result.question_id);
          return (
            <ResultCard
              key={result.question_id}
              result={result}
              questionText={question?.text ?? ""}
              index={i}
            />
          );
        })}
      </div>

      <button className={styles.retryBtn} onClick={onRetry}>
        Analyze another paper
      </button>
    </div>
  );
}