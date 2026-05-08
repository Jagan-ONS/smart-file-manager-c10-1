function buildUrl(path, params) {
  const url = new URL(path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    }
  }
  return url.toString();
}

export async function fetchTree(path = "") {
  const res = await fetch(buildUrl("/tree", { path }));
  if (!res.ok) throw new Error(`tree failed: ${res.status} ${res.statusText}`);
  return await res.json();
}

export async function fetchPreview(path) {
  const res = await fetch(buildUrl("/preview", { path }));
  if (!res.ok) throw new Error(`preview failed: ${res.status} ${res.statusText}`);
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return await res.json();
  return { path, content: await res.text(), contentType: ct };
}

function safeJsonParse(str) {
  try {
    return JSON.parse(str);
  } catch {
    return str;
  }
}

export async function streamChat({ message, signal, onEvent }) {
  const res = await fetch("/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message }),
    signal
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`chat failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ""}`);
  }

  if (!res.body) throw new Error("chat failed: missing response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  let buf = "";
  let eventName = "message";
  let dataLines = [];

  const flushEvent = () => {
    if (!dataLines.length) return;
    const dataRaw = dataLines.join("\n");
    const data = safeJsonParse(dataRaw);
    onEvent?.({ event: eventName, data, raw: dataRaw });
    dataLines = [];
    eventName = "message";
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      let line = buf.slice(0, idx);
      buf = buf.slice(idx + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);

      if (line === "") {
        flushEvent();
        continue;
      }

      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim() || "message";
        continue;
      }

      if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
        continue;
      }
    }
  }

  flushEvent();
}

