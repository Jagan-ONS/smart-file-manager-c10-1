import React, { useMemo, useState } from "react";

function formatTs(ts) {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return "";
  }
}

function pretty(v) {
  if (v === undefined) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export default function ToolCallLog({ entries }) {
  const [expanded, setExpanded] = useState(() => new Set());

  const list = useMemo(() => entries || [], [entries]);

  if (!list.length) {
    return <div className="muted">No tool calls yet.</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {list.map((e) => {
        const isOpen = expanded.has(e.id);
        const title =
          e.kind === "tool_call"
            ? `tool_call: ${e.toolCall?.name || e.toolCall?.tool || "(unknown)"}`
            : e.kind === "tool_result"
              ? `tool_result`
              : e.kind || "event";

        const status = e.status || "done";
        const statusColor =
          status === "running"
            ? "rgba(110,168,254,0.9)"
            : status === "error"
              ? "rgba(255,107,107,0.95)"
              : "rgba(255,255,255,0.7)";

        return (
          <div
            key={e.id}
            style={{
              border: "1px solid rgba(255,255,255,0.14)",
              background: "rgba(0,0,0,0.22)",
              borderRadius: 12,
              overflow: "hidden"
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                cursor: "pointer",
                userSelect: "none"
              }}
              onClick={() => {
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(e.id)) next.delete(e.id);
                  else next.add(e.id);
                  return next;
                });
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                <span className="mono" style={{ color: "rgba(255,255,255,0.55)" }}>
                  {isOpen ? "▾" : "▸"}
                </span>
                <span style={{ fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {title}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="mono" style={{ fontSize: 11, color: "rgba(255,255,255,0.55)" }}>
                  {formatTs(e.ts)}
                </span>
                <span className="pill" style={{ borderColor: statusColor, color: statusColor }}>
                  {status}
                </span>
              </div>
            </div>

            {isOpen ? (
              <div style={{ padding: 10, borderTop: "1px solid rgba(255,255,255,0.14)" }}>
                {e.error ? <div className="error" style={{ marginBottom: 8 }}>{pretty(e.error)}</div> : null}
                <pre className="mono" style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                  {e.kind === "tool_call" ? pretty(e.toolCall) : pretty(e.toolResult ?? e)}
                </pre>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

