import { useState } from "react";
import styles from "./ReferenceUpload.module.css";

export default function ReferenceUpload({ onStatusChange }) {
  const [status, setStatus] = useState("idle"); // idle | uploading | success | error
  const [chunksIndexed, setChunksIndexed] = useState(null);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith(".pdf")) {
      setStatus("error");
      return;
    }

    setStatus("uploading");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/upload-reference", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.error) {
        setStatus("error");
        onStatusChange(false);
      } else {
        setStatus("success");
        setChunksIndexed(data.chunks_indexed);
        onStatusChange(true);
      }
    } catch {
      setStatus("error");
      onStatusChange(false);
    }
  }

  async function handleClear() {
    await fetch("http://localhost:8000/upload-reference", { method: "DELETE" });
    setStatus("idle");
    setChunksIndexed(null);
    onStatusChange(false);
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.label}>
        Reference material
        <span className={styles.hint}>optional — improves gap detection</span>
      </div>

      {status === "idle" && (
        <label className={styles.uploadBtn}>
          + Upload textbook / notes PDF
          <input type="file" accept=".pdf" onChange={handleFile} hidden />
        </label>
      )}

      {status === "uploading" && (
        <div className={styles.pill + " " + styles.loading}>
          <span className={styles.spinner} /> Indexing...
        </div>
      )}

      {status === "success" && (
        <div className={styles.pill + " " + styles.success}>
          <span>✓ {chunksIndexed} chunks indexed</span>
          <button className={styles.clearBtn} onClick={handleClear}>✕</button>
        </div>
      )}

      {status === "error" && (
        <div className={styles.pill + " " + styles.error}>
          Upload failed — text-based PDF only
          <button className={styles.clearBtn} onClick={() => setStatus("idle")}>✕</button>
        </div>
      )}
    </div>
  );
}