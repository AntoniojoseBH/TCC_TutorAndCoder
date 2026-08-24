const BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

let _token: string | null = localStorage.getItem("token");

export const setToken = (t: string) => { _token = t; localStorage.setItem("token", t); };
export const getToken = () => _token;
export const clearToken = () => { _token = null; localStorage.removeItem("token"); };

const headers = (extra: Record<string,string> = {}) => ({
  "Content-Type": "application/json",
  ...(  _token ? { Authorization: `Bearer ${_token}` } : {}),
  ...extra,
});

export async function apiPost(path: string, body: any, auth = true) {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (r.status === 401) { clearToken(); window.location.reload(); }
  return r;
}

export async function apiPostForm(path: string, body: Record<string,string>) {
  const form = new URLSearchParams(body);
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  return r;
}

export async function apiGet(path: string) {
  const r = await fetch(`${BASE}${path}`, { headers: headers() });
  if (r.status === 401) { clearToken(); window.location.reload(); }
  return r;
}

export async function apiPatch(path: string, body: any) {
  const r = await fetch(`${BASE}${path}`, {
    method: "PATCH", headers: headers(), body: JSON.stringify(body),
  });
  return r;
}

export async function apiDelete(path: string) {
  const r = await fetch(`${BASE}${path}`, {
    method: "DELETE", headers: headers(),
  });
  return r;
}

export async function* streamChat(message: string, sessionId: string) {
  const r = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line || line === "data: [DONE]") continue;
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "chunk" && data.content) yield data.content as string;
        } catch {}
      }
    }
  }
}
