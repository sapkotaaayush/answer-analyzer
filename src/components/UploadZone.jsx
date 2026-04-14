import { useState, useRef } from "react";

export default function UploadZone({ onUpload }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef(null);

  function handleFile(file) {
    if (!file) return;
    if (file.type !== "application/pdf") {
      alert("Please upload a PDF file.");
      return;
    }
    setIsLoading(true);
    onUpload(file).finally(() => setIsLoading(false));
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }

  return (
    <div className="upload-page">
      <div
        className={`upload-zone ${isDragging ? "dragging" : ""} ${isLoading ? "loading" : ""}`}
        onClick={() => !isLoading && inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          style={{ display: "none" }}
          onChange={(e) => handleFile(e.target.files[0])}
        />

        {isLoading ? (
          <>
            <div className="upload-spinner" />
            <p>Extracting questions...</p>
          </>
        ) : (
          <>
            <div className="upload-icon">📄</div>
            <p className="upload-title">Drop your question paper here</p>
            <p className="upload-sub">or click to browse — PDF only</p>
            <p className="upload-hint">
              Must be a text-based PDF. If you have a scanned or photo copy,
              convert it to PDF using your phone's scanner app first.
            </p>
          </>
        )}
      </div>
    </div>
  );
}