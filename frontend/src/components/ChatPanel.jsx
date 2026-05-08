import React, { useEffect, useMemo, useRef, useState } from "react";
import { streamChat } from "../api.js";

function asText(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function normalizeToolCall(data) {
  if (!data) return null;
  if (data.tool_call) return data.tool_call;
  if (data.toolCall) return data.toolCall;
  if (data.name || data.tool) return data;
  return data;
}

function normalizeToolResult(data) {
  if (!data) return null;
  if (data.tool_result) return data.tool_result;
  if (data.toolResult) return data.toolResult;
  return data;
}

export default function ChatPanel({ onToolCall, onToolResult, onToolError }) {
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState(() => [
    { id: 1, role: "assistant", content: "Hi — ask me to explore files, preview content, or run tools." }
  ]);
  const [streaming, setStreaming] = useState(false);
  const [err, setErr] = useState("");

  const nextId = useRef(2);
  const activeAssistantId = useRef(null);
  const toolIdByKey = useRef(new Map()); // best-effort correlation
  const abortRef = useRef(null);
  const scrollRef = useRef(null);

  const canSend = useMemo(() => input.trim().length > 0 && !streaming, [input, streaming]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs.length, streaming]);

  const appendMsg = (role, content) => {
    const id = nextId.current++;
    setMsgs((prev) => [...prev, { id, role, content }]);
    return id;
  };

  const setAssistantContent = (id, updater) => {
    setMsgs((prev) =>
      prev.map((m) => {
        if (m.id !== id) return m;
        const next = typeof updater === "function" ? updater(m.content) : updater;
        return { ...m, content: next };
      })
    );
  };

  const startAssistant = () => {
    const id = appendMsg("assistant", "");
    activeAssistantId.current = id;
    return id;
  };

  const stopStream = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  };

  const handleEvent = (evt) => {
    const { event, data } = evt;
    if (event === "assistant_delta") {
      const delta = typeof data === "string" ? data : data?.delta ?? data?.text ?? data?.content ?? asText(data);
      if (!activeAssistantId.current) startAssistant();
      setAssistantContent(activeAssistantId.current, (prev) => prev + delta);
      return;
    }

    if (event === "assistant_final") {
      const finalText = typeof data === "string" ? data : data?.text ?? data?.content ?? data?.final ?? null;
      if (finalText !== null && finalText !== undefined) {
        if (!activeAssistantId.current) startAssistant();
        setAssistantContent(activeAssistantId.current, String(finalText));
      }
      setStreaming(false);
      return;
    }

    if (event === "tool_call") {
      const tc = normalizeToolCall(data);
      const toolLogId = onToolCall?.(tc);

      const key =
        tc?.tool_call_id ??
        tc?.id ??
        tc?.toolCallId ??
        tc?.tool_call?.id ??
        tc?.name ??
        `tool-${Date.now()}-${Math.random()}`;
      if (toolLogId != null) toolIdByKey.current.set(key, toolLogId);
      return;
    }

    if (event === "tool_result") {
      const tr = normalizeToolResult(data);
      const key =
        tr?.tool_call_id ??
        tr?.id ??
        tr?.toolCallId ??
        tr?.tool_call?.id ??
        tr?.name;
      const toolLogId = key ? toolIdByKey.current.get(key) : null;
      if (toolLogId != null) {
        onToolResult?.(toolLogId, tr);
      } else {
        console.warn("Unmatched tool_result event", tr);
      }
      return;
    }

    if (event === "error") {
      const msg = typeof data === "string" ? data : data?.message ?? asText(data);
      setErr(msg || "Unknown error");
      setStreaming(false);
      if (activeAssistantId.current) {
        setAssistantContent(activeAssistantId.current, (prev) => prev || "(error)");
      }
      return;
    }
  };

  const send = async () => {
    const msg = input.trim();
    if (!msg) return;
    setErr("");
    setInput("");

    appendMsg("user", msg);
    startAssistant();

    setStreaming(true);
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      await streamChat({
        message: msg,
        signal: ac.signal,
        onEvent: handleEvent
      });
      setStreaming(false);
    } catch (e) {
      if (ac.signal.aborted) return;
      const m = e?.message || String(e);
      setErr(m);
      setStreaming(false);
      onToolError?.(null, m);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div ref={scrollRef} style={{ padding: 12, overflow: "auto", minHeight: 0 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {msgs.map((m) => (
            <div
              key={m.id}
              style={{
                alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "92%",
                border: "1px solid rgba(255,255,255,0.14)",
                background: m.role === "user" ? "rgba(110,168,254,0.16)" : "rgba(0,0,0,0.22)",
                borderRadius: 14,
                padding: "10px 12px"
              }}
            >
              <div className="muted mono" style={{ fontSize: 11, marginBottom: 6 }}>
                {m.role}
              </div>
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.35 }}>{m.content}</div>
            </div>
          ))}
          {streaming ? (
            <div className="muted" style={{ fontSize: 12 }}>
              Streaming…
            </div>
          ) : null}
          {err ? (
            <div className="error" style={{ fontSize: 12 }}>
              {err}
            </div>
          ) : null}
        </div>
      </div>

      <div style={{ padding: 12, borderTop: "1px solid rgba(255,255,255,0.14)" }}>
        <div style={{ display: "flex", gap: 10 }}>
          <input
            className="input"
            value={input}
            placeholder="Type a message…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (canSend) send();
              }
            }}
            disabled={streaming}
          />
          <button className="btn" onClick={send} disabled={!canSend}>
            Send
          </button>
          <button className="btn" onClick={stopStream} disabled={!streaming}>
            Stop
          </button>
        </div>
        <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
          SSE events: <span className="mono">assistant_delta</span>, <span className="mono">tool_call</span>,{" "}
          <span className="mono">tool_result</span>, <span className="mono">assistant_final</span>,{" "}
          <span className="mono">error</span>
        </div>
      </div>
    </div>
  );
}

