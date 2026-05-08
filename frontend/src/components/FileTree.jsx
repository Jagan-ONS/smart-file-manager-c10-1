import React, { useMemo, useState } from "react";

function normalizeTree(tree) {
  // Accepts:
  // - { entries: [...] }
  // - { children: [...] }
  // - [...] (array)
  if (!tree) return [];
  if (Array.isArray(tree)) return tree;
  if (Array.isArray(tree.items)) return tree.items;
  if (Array.isArray(tree.entries)) return tree.entries;
  if (Array.isArray(tree.children)) return tree.children;
  return [];
}

function displayName(node) {
  return node?.name || node?.path || node?.id || "(unnamed)";
}

function nodePath(node) {
  return node?.path || node?.full_path || node?.id || "";
}

function nodeType(node) {
  const t = node?.type || node?.kind;
  if (t === "dir" || t === "directory" || t === "folder") return "dir";
  if (t === "file") return "file";
  if (node?.is_dir === true) return "dir";
  if (node?.is_file === true) return "file";
  // heuristic: directories often have children
  if (Array.isArray(node?.children) || Array.isArray(node?.entries)) return "dir";
  return "file";
}

function TreeNode({ node, level, selectedPath, onSelectPath }) {
  const [open, setOpen] = useState(level < 1);
  const t = nodeType(node);
  const name = displayName(node);
  const p = nodePath(node) || name;
  const children = normalizeTree(node?.children ?? node?.entries);

  const isSelected = selectedPath && p === selectedPath;

  const rowStyle = {
    paddingLeft: 10 + level * 14,
    display: "flex",
    alignItems: "center",
    gap: 8,
    paddingTop: 6,
    paddingBottom: 6,
    borderRadius: 10,
    cursor: "pointer",
    userSelect: "none",
    background: isSelected ? "rgba(110,168,254,0.18)" : "transparent",
    border: isSelected ? "1px solid rgba(110,168,254,0.35)" : "1px solid transparent"
  };

  return (
    <div>
      <div
        style={rowStyle}
        onClick={() => {
          if (t === "dir") setOpen((v) => !v);
          else onSelectPath(p);
        }}
        title={p}
      >
        <span className="mono" style={{ width: 18, color: "rgba(255,255,255,0.55)" }}>
          {t === "dir" ? (open ? "▾" : "▸") : "·"}
        </span>
        <span style={{ color: t === "dir" ? "rgba(255,255,255,0.86)" : "rgba(255,255,255,0.78)" }}>
          {name}
        </span>
        <span style={{ flex: 1 }} />
        <span className="muted mono" style={{ fontSize: 11 }}>
          {t}
        </span>
      </div>

      {t === "dir" && open && children?.length ? (
        <div>
          {children.map((c, idx) => (
            <TreeNode
              key={nodePath(c) || `${level}-${idx}-${displayName(c)}`}
              node={c}
              level={level + 1}
              selectedPath={selectedPath}
              onSelectPath={onSelectPath}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function FileTree({ tree, error, onReload, selectedPath, onSelectPath }) {
  const nodes = useMemo(() => normalizeTree(tree), [tree]);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ padding: 12, borderBottom: "1px solid rgba(255,255,255,0.14)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
          <div>
            <div style={{ fontWeight: 650, fontSize: 13 }}>File tree</div>
            <div className="muted" style={{ fontSize: 12 }}>
              Click a file to preview
            </div>
          </div>
          <button className="btn" onClick={onReload}>
            Reload
          </button>
        </div>
        {error ? (
          <div className="error" style={{ fontSize: 12, marginTop: 8 }}>
            {error}
          </div>
        ) : null}
      </div>

      <div style={{ padding: 10, overflow: "auto", minHeight: 0 }}>
        {nodes?.length ? (
          nodes.map((n, idx) => (
            <TreeNode
              key={nodePath(n) || `root-${idx}-${displayName(n)}`}
              node={n}
              level={0}
              selectedPath={selectedPath}
              onSelectPath={onSelectPath}
            />
          ))
        ) : (
          <div className="muted" style={{ padding: 10 }}>
            {tree ? "No entries" : "Loading..."}
          </div>
        )}
      </div>
    </div>
  );
}

