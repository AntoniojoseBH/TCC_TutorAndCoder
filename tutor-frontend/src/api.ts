const BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

let _token: string | null = localStorage.getItem("token");

export const setToken = (t: string) => { _token = t; localStorage.setItem("token", t); };
export const getToken = () => _token;
export const clearToken = () => { _token = null; localStorage.removeItem("token"); };

const headers = (extra: Record<string,string> = {}) => ({
  "Content-Type": "application/json",
  // Pula a página de aviso interstitial do plano gratuito da Ngrok, que
  // intercepta chamadas de API em segundo plano (fetch) além de navegação
  // normal — sem isso, o GET real nunca chega ao backend, só o preflight
  // OPTIONS, travando o app (ex: após o login, ficar preso na tela).
  "ngrok-skip-browser-warning": "true",
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
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "ngrok-skip-browser-warning": "true",
    },
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

// Anexo enviado junto com uma mensagem — imagem ou documento (PDF/texto),
// sempre em base64, no formato aceito nativamente pela API multimodal da Anthropic.
export interface ChatAttachment {
  filename: string;
  media_type: string; // ex: "image/png", "application/pdf", "text/plain"
  data: string;        // conteúdo em base64, sem o prefixo "data:...;base64,"
}

export async function* streamChat(
  message: string,
  sessionId: string,
  attachment?: ChatAttachment | null
) {
  const r = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      message,
      session_id: sessionId,
      ...(attachment ? { attachment } : {}),
    }),
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
