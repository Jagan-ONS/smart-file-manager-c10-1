import React, { useEffect, useMemo, useRef, useState } from "react";
import { fetchPreview, fetchTree } from "./api.js";
import FileTree from "./components/FileTree.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import ToolCallLog from "./components/ToolCallLog.jsx";
import FilePreview from "./components/FilePreview.jsx";

export default function App() {
  const [tree, setTree] = useState(null);
  const [treeError, setTreeError] = useState("");
  const [selectedPath, setSelectedPath] = useState("");

  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  const [toolLog, setToolLog] = useState([]);

  const apiBase = useMemo(() => {
    // purely informational: requests are proxied by Vite in dev
    return import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
  }, []);

  //learn 
  const toolSeq = useRef(1);

  const pushTool = (entry) => {
    const id = toolSeq.current++;
    setToolLog((prev) => [{ id, ts: Date.now(), ...entry }, ...prev]);
    return id;
  };

  const patchTool = (id, patch) => {
    setToolLog((prev) => prev.map((e) => (e.id === id ? { ...e, ...patch } : e)));
  };

  const reloadTree = async () => {
    setTreeError("");
    try {
      const t = await fetchTree("");
      setTree(t);
    } catch (e) {
      setTreeError(e?.message || String(e));
    }
  };

  useEffect(() => {
    reloadTree();
  }, []);

  useEffect(() => {
    //why we are using function inside a function 
    //what is the clousure issue here ? 
    
    const run = async () => {
      if (!selectedPath) {
        setPreview(null);
        setPreviewError("");
        return;
      }
      setPreviewLoading(true);
      setPreviewError("");
      try {
        const p = await fetchPreview(selectedPath);
        setPreview(p);
      } catch (e) {
        setPreview(null);
        setPreviewError(e?.message || String(e));
      } finally {
        setPreviewLoading(false);
      }
    };
    run();
  }, [selectedPath]);

  return (
    <div className="app">
      <div className="topbar">
        <div className="title">Smart File Manager</div>
        <div className="meta">
          <span className="pill">API: {apiBase}</span>
        </div>
      </div>

      <div className="content">
        <div className="panel">
          <FileTree
            tree={tree}
            error={treeError}
            onReload={reloadTree}
            selectedPath={selectedPath}
            onSelectPath={setSelectedPath}
          />
        </div>

        <div className="right">
          <div className="rightTop">
            <div className="card">
              <div className="cardHeader">
                <div>
                  <div className="h">Chat</div>
                  <div className="sub">Streams server events</div>
                </div>
              </div>
              <div className="cardBody" style={{ padding: 0 }}>
                <ChatPanel
                  onToolCall={(tc) => pushTool({ kind: "tool_call", toolCall: tc, status: "running" })}
                  onToolResult={(id, tr) => patchTool(id, { kind: "tool_result", toolResult: tr, status: "done" })}
                  onToolError={(id, err) => patchTool(id, { status: "error", error: err })}
                />
              </div>
            </div>

            <div className="card">
              <div className="cardHeader">
                <div>
                  <div className="h">File preview</div>
                  <div className="sub mono">{selectedPath || "—"}</div>
                </div>
              </div>
              <div className="cardBody">
                <FilePreview loading={previewLoading} error={previewError} preview={preview} />
              </div>
            </div>
          </div>

          <div style={{ padding: 12, paddingTop: 0, minHeight: 0 }}>
            <div className="card" style={{ height: "100%" }}>
              <div className="cardHeader">
                <div>
                  <div className="h">Tool call log</div>
                  <div className="sub">Calls + results from chat</div>
                </div>
              </div>
              <div className="cardBody">
                <ToolCallLog entries={toolLog} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

