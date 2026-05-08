import React, { useMemo } from "react";

function extractPreview(preview) {
  if (!preview) return { path: "", content: "", contentType: "" };
  if (typeof preview === "string") return { path: "", content: preview, contentType: "text/plain" };
  const path = preview.path || preview.file || preview.filename || "";
  const content = preview.content ?? preview.text ?? preview.data ?? "";
  const contentType = preview.contentType || preview.mime || preview.mimetype || "";
  return { path, content, contentType };
}

export default function FilePreview({ loading, error, preview }) {
  const p = useMemo(() => extractPreview(preview), [preview]);

  if (loading) return <div className="muted">Loading preview…</div>;
  if (error) return <div className="error">{error}</div>;
  if (!preview) return <div className="muted">Select a file from the tree.</div>;

  const isProbablyCode =
    (p.contentType && p.contentType.includes("text/")) ||
    (typeof p.content === "string" && p.content.includes("\n"));

  if (!isProbablyCode) {
    return (
      <div>
        <div className="muted" style={{ marginBottom: 8 }}>
          Non-text preview
        </div>
        <pre className="mono" style={{ whiteSpace: "pre-wrap", margin: 0 }}>
          {typeof p.content === "string" ? p.content : JSON.stringify(p.content, null, 2)}
        </pre>
      </div>
    );
  }

  return (
    <pre
      className="mono"
      style={{
        margin: 0,
        whiteSpace: "pre",
        overflow: "auto",
        background: "rgba(0,0,0,0.35)",
        border: "1px solid rgba(255,255,255,0.14)",
        borderRadius: 12,
        padding: 12
      }}
    >
      {typeof p.content === "string" ? p.content : JSON.stringify(p.content, null, 2)}
    </pre>
  );
}

