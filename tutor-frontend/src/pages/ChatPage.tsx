import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { apiGet, apiPost, apiPatch, apiDelete, streamChat, ChatAttachment } from "../api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import mermaid from "mermaid";
import { Plus, Search, MoreVertical, Edit2, Trash2, X, Send, Check, Paperclip, FileText } from "lucide-react";

mermaid.initialize({ startOnLoad: false, theme: "dark", securityLevel: "loose" });

interface Session { session_id: string; title: string; started_at: string; message_count: number; }
interface Message {
  role: string;
  content: string;
  attachment?: { filename: string; media_type: string; previewUrl?: string };
}

const THINKING = ["Analisando sua pergunta...", "Consultando os agentes...", "Elaborando a resposta...", "Preparando exemplos..."];

function ThinkingDots() {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i+1) % THINKING.length), 2500);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="flex items-center gap-3 p-3 bg-panel rounded-xl border border-border max-w-xs">
      <div className="flex gap-1">
        {[0,1,2].map(i => (
          <div key={i} className="w-2 h-2 rounded-full bg-accent dot-bounce"
            style={{ animationDelay: `${i*0.16}s` }} />
        ))}
      </div>
      <span className="text-muted text-sm">{THINKING[idx]}</span>
    </div>
  );
}

// Renderiza diagramas Mermaid (fluxogramas, grafos, árvores) em SVG real,
// evitando que a IA precise "desenhar" ASCII à mão — tarefa em que LLMs
// cometem erros estruturais frequentes por não conseguir revisar
// visualmente o que já foi gerado.
function MermaidDiagram({ code }: { code: string }) {
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState(false);
  const idRef = useRef(`mermaid-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      try {
        // Valida a sintaxe ANTES de renderizar. O mermaid.render() sozinho
        // não rejeita a Promise em caso de sintaxe inválida — em vez disso,
        // resolve "com sucesso" retornando um SVG que É o próprio desenho
        // de erro (ícone de bomba vermelha), que nosso .catch() nunca pegava.
        // mermaid.parse() sim rejeita corretamente nesse caso.
        await mermaid.parse(code);
        const result = await mermaid.render(idRef.current, code);
        if (!cancelled) { setSvg(result.svg); setError(false); }
      } catch {
        if (!cancelled) setError(true);
      }
    }

    renderDiagram();
    return () => { cancelled = true; };
  }, [code]);

  if (error) {
    // Enquanto a resposta ainda está sendo transmitida (streaming), o código
    // mermaid pode estar incompleto e falhar — mostramos o texto bruto até
    // a sintaxe ficar completa e válida.
    return (
      <div className="rounded-lg border border-border overflow-hidden my-2">
        <div className="px-3 py-1.5 bg-panel border-b border-border text-xs text-muted">diagrama</div>
        <pre className="p-3 text-xs text-muted overflow-x-auto whitespace-pre-wrap font-mono">{code}</pre>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-panel my-2 p-4 overflow-x-auto flex justify-center"
      dangerouslySetInnerHTML={{ __html: svg }} />
  );
}

function CodeBlock({ className, children }: any) {
  const [copied, setCopied] = useState(false);
  const lang = /language-(\w+)/.exec(className||"")?.[1] || "text";
  const code = String(children).replace(/\n$/,"");
  function copy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <div className="relative group rounded-lg overflow-hidden border border-border my-2">
      <div className="flex items-center justify-between px-3 py-1.5 bg-panel border-b border-border">
        <span className="text-xs text-muted font-mono">{lang}</span>
        <button onClick={copy} className="text-xs text-muted hover:text-text transition-colors flex items-center gap-1">
          {copied ? <><Check size={12}/> Copiado!</> : "Copiar"}
        </button>
      </div>
      <SyntaxHighlighter language={lang} style={vscDarkPlus}
        customStyle={{ margin:0, background:"#0f1117", fontSize:"0.82rem", padding:"12px 16px" }}>
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

// Highlights matching text within any React children tree
function highlightChildren(children: React.ReactNode, term: string): React.ReactNode {
  if (!term) return children;
  return React.Children.map(children, child => {
    if (typeof child === "string") {
      const parts = child.split(new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));
      if (parts.length === 1) return child;
      return parts.map((part, i) =>
        part.toLowerCase() === term.toLowerCase()
          ? <mark key={i} className="search-highlight"
              style={{background:"#fbbf24",color:"#000",borderRadius:"2px",padding:"0 1px"}}>{part}</mark>
          : part
      );
    }
    if (React.isValidElement(child) && (child.props as any).children) {
      return React.cloneElement(child as React.ReactElement<any>, {},
        highlightChildren((child.props as any).children, term));
    }
    return child;
  });
}

// Conserta tabelas Markdown malformadas ANTES de renderizar, independente
// de a IA ter seguido corretamente as instruções de formatação ou não.
// Cobre dois padrões observados na prática:
//   1) Falta a linha separadora obrigatória (|---|---|) entre cabeçalho e corpo
//   2) Linhas "ruído" contendo só "|" soltos entre o cabeçalho e os dados
// Esse reparo só age logo após uma linha identificada como cabeçalho de
// tabela (linha "|...|" que não é precedida por outra linha de tabela),
// minimizando o risco de mexer em conteúdo de texto comum que use "|".
function repairMarkdownTables(text: string): string {
  const lines = text.split("\n");
  const result: string[] = [];
  const isTableRow = (l: string) => /^\s*\|.*\|\s*$/.test(l) && l.replace(/\|/g, "").trim().length > 0;
  const isNoiseRow = (l: string) => /^\s*\|\s*\|?\s*$/.test(l); // linha só com "|" solto(s)
  const isBlankLine = (l: string) => l.trim() === "";
  const isValidSeparator = (l: string) => /^\s*\|?[\s:|-]+\|?\s*$/.test(l) && l.includes("-");

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const prevWasTableRow = result.length > 0 && isTableRow(result[result.length - 1]);

    if (isTableRow(line) && !prevWasTableRow) {
      // Encontrou o início de uma tabela (linha de cabeçalho)
      result.push(line);
      const colCount = line.split("|").filter((c, idx, arr) =>
        !(idx === 0 && c.trim() === "") && !(idx === arr.length - 1 && c.trim() === "")
      ).length;

      // Pula linhas de ruído (só "|" solto, OU linhas em branco intercaladas
      // entre elas) logo após o cabeçalho
      let j = i + 1;
      while (j < lines.length && (isNoiseRow(lines[j]) || isBlankLine(lines[j]))) j++;

      if (j < lines.length && isValidSeparator(lines[j])) {
        result.push(lines[j]);
        j++;
      } else {
        // Insere a linha separadora que faltava
        result.push("|" + Array(Math.max(colCount, 1)).fill("---").join("|") + "|");
      }
      i = j;
      continue;
    }

    result.push(line);
    i++;
  }
  return result.join("\n");
}

function MsgContent({ content, highlight }: { content: string; highlight?: string }) {
  const hl = highlight && highlight.trim() ? highlight : undefined;
  const safeContent = repairMarkdownTables(content);

  const makeWrapper = (Tag: string) => ({ children, ...props }: any) => (
    <Tag {...props}>{hl ? highlightChildren(children, hl) : children}</Tag>
  );

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}
      components={{
        code: ({ node, className, children, ...p }: any) => {
          // A partir do react-markdown v9, a prop "inline" não é mais enviada
          // (mudança de comportamento da própria biblioteca). O jeito correto
          // de diferenciar agora é pela presença de className com "language-":
          // blocos de código (```texto```) sempre recebem essa classe;
          // código inline (`texto`) nunca recebe.
          const hasLanguageClass = /language-(\w+)/.test(className || "");
          const lang = /language-(\w+)/.exec(className || "")?.[1] || "text";
          const isInlineCode = !hasLanguageClass;

          if (!isInlineCode && lang === "mermaid") {
            const code = String(children).replace(/\n$/, "");
            return <MermaidDiagram code={code} />;
          }
          return isInlineCode
            ? <code className="bg-panel text-accent px-1 py-0.5 rounded text-xs font-mono" {...p}>{children}</code>
            : <CodeBlock className={className}>{children}</CodeBlock>;
        },
        p:          makeWrapper("p"),
        h1:         makeWrapper("h1"),
        h2:         makeWrapper("h2"),
        h3:         makeWrapper("h3"),
        h4:         makeWrapper("h4"),
        li:         makeWrapper("li"),
        td:         makeWrapper("td"),
        th:         makeWrapper("th"),
        blockquote: makeWrapper("blockquote"),
        strong:     makeWrapper("strong"),
        em:         makeWrapper("em"),
      }}>
      {safeContent}
    </ReactMarkdown>
  );
}

function FeedbackRow({ sessionId, msgIndex }: { sessionId: string; msgIndex: number }) {
  const [rated, setRated] = useState(false);
  const emojis = ["😞","😕","😐","😊","🤩"];
  async function rate(v: number) {
    await apiPost("/metrics/feedback", { session_id: sessionId, rating: v, comment: `Resposta #${msgIndex}` });
    setRated(true);
  }
  if (rated) return <span className="text-xs text-green-400 ml-1">✓ Avaliação registrada</span>;
  return (
    <div className="flex items-center gap-1 mt-1.5">
      <span className="text-xs text-muted mr-1">Útil?</span>
      {emojis.map((e,i) => (
        <button key={i} onClick={() => rate(i+1)}
          className="text-base hover:scale-125 transition-transform" title={`${i+1} estrela(s)`}>{e}</button>
      ))}
    </div>
  );
}

export default function ChatPage() {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [search, setSearch] = useState("");
  const [ctrlf, setCtrlf] = useState("");
  const [matchIndex, setMatchIndex] = useState(0);
  const [menuSid, setMenuSid] = useState<string|null>(null);
  const [renamingSid, setRenamingSid] = useState<string|null>(null);
  const [renameVal, setRenameVal] = useState("");
  const [deletingSid, setDeletingSid] = useState<string|null>(null);
  const [lastFeedbackIdx, setLastFeedbackIdx] = useState<number|null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sendingRef = useRef(false); // trava síncrona contra duplo envio
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Anexo selecionado, pronto para ser enviado junto com a próxima mensagem
  const [attachment, setAttachment] = useState<ChatAttachment | null>(null);
  const [attachmentPreview, setAttachmentPreview] = useState<string | null>(null); // URL local só para imagens
  const [attachError, setAttachError] = useState("");

  const MAX_ATTACHMENT_MB = 10;
  const ACCEPTED_TYPES = [
    "image/png", "image/jpeg", "image/webp", "image/gif",
    "application/pdf",
    "text/plain", "text/markdown", "text/x-python", "text/javascript",
    "application/json",
  ];

  function handleAttachClick() {
    fileInputRef.current?.click();
  }

  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // permite selecionar o mesmo arquivo de novo depois
    if (!file) return;
    setAttachError("");

    if (file.size > MAX_ATTACHMENT_MB * 1024 * 1024) {
      setAttachError(`Arquivo muito grande (máximo ${MAX_ATTACHMENT_MB}MB).`);
      return;
    }

    // Detecta o tipo mesmo quando o navegador não preenche file.type
    // (comum em .py, .md em alguns sistemas)
    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    const extToType: Record<string, string> = {
      py: "text/x-python", js: "text/javascript", ts: "text/plain",
      md: "text/markdown", txt: "text/plain", json: "application/json",
      java: "text/plain", c: "text/plain", cpp: "text/plain",
    };
    const mediaType = file.type || extToType[ext] || "text/plain";

    const isImage = mediaType.startsWith("image/");
    const isKnown = ACCEPTED_TYPES.includes(mediaType) || extToType[ext];

    if (!isKnown) {
      setAttachError("Tipo de arquivo não suportado. Envie imagem, PDF ou arquivo de texto/código.");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1] || "";
      setAttachment({ filename: file.name, media_type: mediaType, data: base64 });
      setAttachmentPreview(isImage ? result : null);
    };
    reader.onerror = () => setAttachError("Não foi possível ler o arquivo.");
    reader.readAsDataURL(file);
  }

  function clearAttachment() {
    setAttachment(null);
    setAttachmentPreview(null);
    setAttachError("");
  }

  useEffect(() => { loadSessions(); }, []);
  useEffect(() => { scrollToBottom(); }, [messages, streaming]);

  // Scroll to the current match highlight
  useEffect(() => {
    if (!ctrlf) return;
    const marks = document.querySelectorAll(".search-highlight");
    if (marks.length === 0) return;
    const idx = matchIndex % marks.length;
    marks[idx].scrollIntoView({ behavior: "smooth", block: "center" });
    // Make current match more visible
    marks.forEach((m, i) => {
      (m as HTMLElement).style.background = i === idx ? "#f97316" : "#fbbf24";
      (m as HTMLElement).style.color = "#000";
    });
  }, [matchIndex, ctrlf, messages]);

  function scrollToBottom() {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  async function loadSessions() {
    const r = await apiGet("/chat/sessions");
    if (r.ok) setSessions((await r.json()).sessions || []);
  }

  async function openSession(sid: string) {
    const r = await apiGet(`/chat/history-db/${sid}`);
    if (r.ok) {
      const d = await r.json();
      setMessages(d.messages || []);
      setSessionId(sid);
      setLastFeedbackIdx(null);
    }
    setMenuSid(null);
  }

  function newChat() {
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setLastFeedbackIdx(null);
    setMenuSid(null);
  }


  function buildContext(msgs: Message[], prompt: string) {
    const hist = msgs.slice(-6).filter(m => m.role !== "system");
    if (!hist.length) return prompt;
    const ctx = hist.map(m => `${m.role === "user" ? "Estudante" : "Tutor"}: ${m.content.slice(0,500)}`).join("\n");
    return `[HISTÓRICO RECENTE]\n${ctx}\n\n[NOVA MENSAGEM DO ESTUDANTE]\n${prompt}`;
  }

  async function sendMessage() {
    // Trava síncrona via ref — evita duplo envio quando o Enter dispara
    // duas vezes antes do estado "streaming" (assíncrono) ser atualizado.
    // Permite enviar só o anexo, sem texto (ex: um print sem legenda).
    if ((!input.trim() && !attachment) || streaming || sendingRef.current) return;
    sendingRef.current = true;

    const prompt = input.trim();
    const pendingAttachment = attachment; // captura antes de limpar o estado
    setInput("");
    clearAttachment();
    // Reseta a altura do campo de texto manualmente — o auto-resize ajusta
    // a altura via DOM direto (fora do controle do React), então limpar o
    // valor via setInput não é suficiente para encolher o campo de volta.
    if (inputRef.current) inputRef.current.style.height = "auto";

    const userMsg: Message = {
      role: "user",
      content: prompt || `📎 ${pendingAttachment?.filename}`,
      attachment: pendingAttachment
        ? {
            filename: pendingAttachment.filename,
            media_type: pendingAttachment.media_type,
            previewUrl: pendingAttachment.media_type.startsWith("image/")
              ? `data:${pendingAttachment.media_type};base64,${pendingAttachment.data}`
              : undefined,
          }
        : undefined,
    };
    const newMsgs = [...messages, userMsg];
    setMessages(newMsgs);
    setStreaming(true);

    // Save user message (o anexo em si não é persistido no histórico ainda —
    // fica disponível só durante a sessão atual do navegador)
    apiPost("/chat/save-message", { session_id: sessionId, role: "user", content: userMsg.content });

    let accumulated = "";
    const startTime = Date.now();
    try {
      const fullMsg = buildContext(newMsgs, prompt || `[Arquivo anexado: ${pendingAttachment?.filename}]`);
      setMessages(m => [...m, { role: "assistant", content: "" }]);
      for await (const chunk of streamChat(fullMsg, sessionId, pendingAttachment)) {
        accumulated += chunk;
        const current = accumulated;
        setMessages(m => {
          const copy = [...m];
          copy[copy.length-1] = { role: "assistant", content: current };
          return copy;
        });
      }
    } catch (e) {
      accumulated = `⚠️ Erro: ${e}`;
      const errMsg = accumulated;
      setMessages(m => { const c=[...m]; c[c.length-1]={role:"assistant",content:errMsg}; return c; });
    }

    const elapsed = Date.now() - startTime;
    if (accumulated) {
      apiPost("/chat/save-message", { session_id: sessionId, role: "assistant", content: accumulated, response_time_ms: elapsed });
      setLastFeedbackIdx(newMsgs.length);
    }
    setStreaming(false);
    sendingRef.current = false;
    loadSessions();
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (e.repeat) return; // ignora auto-repeat do teclado (tecla segurada)
      sendMessage();
    }
  }

  async function renameSession(sid: string) {
    if (!renameVal.trim()) return;
    await apiPatch(`/chat/session/${sid}/rename`, { name: renameVal });
    setRenamingSid(null); setMenuSid(null); loadSessions();
  }

  async function deleteSession(sid: string) {
    await apiDelete(`/chat/session-full/${sid}`);
    if (sessionId === sid) newChat();
    setDeletingSid(null); setMenuSid(null); loadSessions();
  }

  const filtered = sessions.filter(s =>
    !search || (s.title||"").toLowerCase().includes(search.toLowerCase())
  );



  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar de conversas ─────────────────────────────────── */}
      <div className="w-64 flex-shrink-0 bg-surface border-r border-border flex flex-col">
        <div className="p-3 border-b border-border space-y-2">
          <button onClick={newChat}
            className="w-full flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover
              text-white text-sm font-medium py-2 rounded-lg transition-colors">
            <Plus size={15}/> Nova conversa
          </button>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none"/>
            <input value={search} onChange={e=>setSearch(e.target.value)}
              placeholder="Buscar conversa..."
              className="w-full bg-bg border border-border rounded-lg pl-9 pr-8 py-1.5
                text-sm text-text focus:outline-none focus:border-accent" />
            {search && (
              <button onClick={() => setSearch("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-text">
                <X size={13}/>
              </button>
            )}
          </div>
        </div>

        {/* Lista de sessões */}
        <div className="flex-1 overflow-y-auto py-2">
          {filtered.length === 0 && (
            <p className="text-muted text-xs text-center py-8 px-4">
              {search ? "Nenhuma conversa encontrada." : "Nenhuma conversa ainda."}
            </p>
          )}
          {filtered.map(s => (
            <div key={s.session_id}
              className={`group relative mx-2 mb-0.5 rounded-lg transition-colors
                ${sessionId===s.session_id ? "bg-white/10" : "hover:bg-panel"}`}>

              {renamingSid===s.session_id ? (
                /* Campo de renomear ocupa o mesmo lugar do título */
                <div className="flex items-center gap-1 px-3 py-2 mx-0">
                  <input value={renameVal} onChange={e=>setRenameVal(e.target.value)} autoFocus
                    onKeyDown={e=>{ if(e.key==="Enter") renameSession(s.session_id); if(e.key==="Escape") setRenamingSid(null); }}
                    className="flex-1 bg-bg border border-accent rounded px-2 py-1 text-sm text-text
                      focus:outline-none min-w-0"/>
                  <button onClick={()=>renameSession(s.session_id)}
                    className="p-1 bg-accent rounded text-white flex-shrink-0"><Check size={12}/></button>
                  <button onClick={()=>setRenamingSid(null)}
                    className="p-1 text-muted hover:text-text flex-shrink-0"><X size={12}/></button>
                </div>
              ) : (
                <>
                  {/* Título clicável */}
                  <button onClick={() => openSession(s.session_id)}
                    className="w-full text-left px-3 py-2.5 pr-8">
                    <p className={`text-sm truncate leading-tight
                      ${sessionId===s.session_id ? "text-white font-medium" : "text-text"}`}>
                      {s.title || "Nova conversa"}
                    </p>
                    <p className="text-xs text-muted mt-0.5">{s.started_at} · {s.message_count} msgs</p>
                  </button>

                  {/* Botão de mais ações — sempre visível */}
                  <button onClick={(e) => { e.stopPropagation(); setMenuSid(menuSid===s.session_id?null:s.session_id); }}
                    className={`absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded transition-colors
                      text-muted hover:text-text
                      ${menuSid===s.session_id ? "text-text bg-panel" : ""}`}>
                    <MoreVertical size={14}/>
                  </button>

                  {/* Menu popup */}
                  {menuSid===s.session_id && (
                    <div className="absolute right-0 top-full mt-1 w-44 bg-panel border border-border
                      rounded-lg shadow-xl z-50 overflow-hidden">
                      <button onClick={() => { setRenamingSid(s.session_id); setRenameVal(s.title||""); setMenuSid(null); }}
                        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-text
                          hover:bg-surface transition-colors">
                        <Edit2 size={13} className="text-muted"/> Renomear
                      </button>
                      <button onClick={() => { setDeletingSid(s.session_id); setMenuSid(null); }}
                        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-danger
                          hover:bg-danger/10 transition-colors">
                        <Trash2 size={13}/> Excluir
                      </button>
                    </div>
                  )}
                </>
              )}

              {/* Delete confirm */}
              {deletingSid===s.session_id && (
                <div className="mx-2 mb-2 bg-danger/10 border border-danger/30 rounded-lg p-2.5">
                  <p className="text-xs text-text mb-2">Excluir esta conversa?</p>
                  <div className="flex gap-1.5">
                    <button onClick={()=>deleteSession(s.session_id)}
                      className="flex-1 bg-danger text-white text-xs py-1 rounded hover:bg-red-600">Excluir</button>
                    <button onClick={()=>setDeletingSid(null)}
                      className="flex-1 bg-panel text-muted text-xs py-1 rounded hover:text-text">Cancelar</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Área principal do chat ────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header — mostra o nome da conversa atual */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
          <h1 className="font-semibold text-text truncate">
            {sessions.find(s => s.session_id === sessionId)?.title || "Nova conversa"}
          </h1>
        </div>

        {/* Busca dentro da conversa — sempre visível */}
        <div className="flex items-center gap-2 px-4 py-2 bg-panel border-b border-border">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"/>
            <input value={ctrlf} onChange={e=>{ setCtrlf(e.target.value); setMatchIndex(0); }}
              placeholder="Buscar conteúdo dentro da conversa..."
              className="w-full bg-transparent pl-8 text-sm text-text focus:outline-none"
              onKeyDown={e => {
                if (e.key === "Enter") {
                  let total = 0;
                  if (ctrlf) {
                    messages.forEach(m => {
                      const matches = m.content.match(new RegExp(ctrlf, "gi"));
                      total += matches ? matches.length : 0;
                    });
                  }
                  setMatchIndex(i => e.shiftKey ? (i - 1 + total) % total : (i + 1) % total);
                }
              }}/>
          </div>
            {ctrlf && (() => {
              let total = 0;
              const safeCtrlf2 = ctrlf.replace(/[.*+?^${}()|\[\]\\]/g, "\\$&");
              messages.forEach(m => {
                const hits = m.content.match(new RegExp(safeCtrlf2, "gi"));
                total += hits ? hits.length : 0;
              });
              return (
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted whitespace-nowrap">
                    {total === 0 ? "Sem resultados" : `${Math.min(matchIndex + 1, total)} / ${total}`}
                  </span>
                  <button onClick={() => setMatchIndex(i => (i - 1 + total) % Math.max(total,1))}
                    disabled={total === 0}
                    className="p-1 text-muted hover:text-text disabled:opacity-30 transition-colors">
                    ▲
                  </button>
                  <button onClick={() => setMatchIndex(i => (i + 1) % Math.max(total,1))}
                    disabled={total === 0}
                    className="p-1 text-muted hover:text-text disabled:opacity-30 transition-colors">
                    ▼
                  </button>
                </div>
              );
            })()}
            {ctrlf && (
              <button onClick={()=>{ setCtrlf(""); setMatchIndex(0); }}
                className="text-muted hover:text-text flex-shrink-0">
                <X size={14}/>
              </button>
            )}
          </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {messages.length === 0 && !streaming && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-5xl mb-4">🤖</div>
              <h2 className="text-xl font-semibold text-text mb-2">Olá, {user?.name}!</h2>
              <p className="text-muted max-w-md">
                Posso te ajudar com programação, redes, SO, IHC,
                banco de dados, engenharia de software e muito mais.
              </p>
              <p className="text-soft text-sm mt-3 font-medium">Digite sua pergunta abaixo para começar.</p>
            </div>
          )}

          {messages.map((msg, i) => {
            const isLast = i === messages.length - 1;
            const isAssistant = msg.role === "assistant";
            return (
              <div key={i} className={`flex ${isAssistant ? "justify-start" : "justify-end"}`}>
                <div className={`flex gap-3 max-w-3xl ${isAssistant ? "" : "flex-row-reverse"}`}>
                  {/* Avatar */}
                  <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm
                    ${isAssistant ? "bg-accent/20 text-accent" : "bg-soft/20 text-soft"}`}>
                    {isAssistant ? "🤖" : user?.name?.charAt(0).toUpperCase()}
                  </div>
                  {/* Bubble */}
                  <div className={`rounded-xl px-4 py-3 ${isAssistant
                    ? "bg-surface border border-border prose max-w-none"
                    : "bg-accent text-white"}`}>
                    {isAssistant
                      ? <MsgContent content={msg.content} highlight={ctrlf || undefined}/>
                      : (
                        <>
                          {msg.attachment && (
                            msg.attachment.previewUrl ? (
                              <img src={msg.attachment.previewUrl} alt={msg.attachment.filename}
                                className="max-w-full max-h-64 rounded-lg mb-2 border border-white/20"/>
                            ) : (
                              <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-2 mb-2">
                                <FileText size={16} className="flex-shrink-0"/>
                                <span className="text-xs truncate">{msg.attachment.filename}</span>
                              </div>
                            )
                          )}
                          <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                        </>
                      )
                    }
                    {/* Streaming cursor */}
                    {isAssistant && isLast && streaming && msg.content &&
                      <span className="inline-block w-0.5 h-4 bg-accent ml-0.5 blink"/>}
                    {/* Feedback */}
                    {isAssistant && isLast && !streaming && lastFeedbackIdx !== null && (
                      <FeedbackRow sessionId={sessionId} msgIndex={i}/>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {streaming && messages[messages.length-1]?.content === "" && (
            <div className="flex justify-start">
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">🤖</div>
                <ThinkingDots/>
              </div>
            </div>
          )}
          <div ref={messagesEndRef}/>
        </div>

        {/* Input */}
        <div className="border-t border-border bg-surface px-4 py-3">
          {/* Prévia do anexo selecionado, antes de enviar */}
          {attachment && (
            <div className="flex items-center gap-2 mb-2 bg-bg border border-border rounded-lg px-3 py-2">
              {attachmentPreview ? (
                <img src={attachmentPreview} alt={attachment.filename}
                  className="w-10 h-10 object-cover rounded flex-shrink-0"/>
              ) : (
                <div className="w-10 h-10 rounded bg-panel flex items-center justify-center flex-shrink-0">
                  <FileText size={16} className="text-muted"/>
                </div>
              )}
              <span className="text-xs text-soft truncate flex-1">{attachment.filename}</span>
              <button onClick={clearAttachment} className="text-muted hover:text-danger flex-shrink-0">
                <X size={14}/>
              </button>
            </div>
          )}
          {attachError && <p className="text-danger text-xs mb-2">{attachError}</p>}

          <div className="flex items-end gap-3 bg-bg border border-border rounded-xl p-3
            focus-within:border-accent transition-colors">
            <input ref={fileInputRef} type="file" className="hidden"
              accept="image/png,image/jpeg,image/webp,image/gif,application/pdf,.txt,.md,.py,.js,.ts,.json,.java,.c,.cpp"
              onChange={handleFileSelected}/>
            <button onClick={handleAttachClick} disabled={streaming} title="Anexar arquivo"
              className="p-1.5 text-muted hover:text-text transition-colors disabled:opacity-40 flex-shrink-0">
              <Paperclip size={17}/>
            </button>
            <textarea ref={inputRef} value={input} onChange={e=>setInput(e.target.value)}
              onKeyDown={handleKey} rows={1} disabled={streaming}
              placeholder="Pergunte algo, cole um código, ou peça para criar um projeto..."
              className="flex-1 bg-transparent text-text text-sm resize-none focus:outline-none
                max-h-40 overflow-y-auto placeholder-muted disabled:opacity-50"
              style={{ minHeight: "24px" }}
              onInput={e => {
                const t = e.target as HTMLTextAreaElement;
                t.style.height = "auto";
                t.style.height = Math.min(t.scrollHeight, 160) + "px";
              }}/>
            <button onClick={sendMessage} disabled={(!input.trim() && !attachment) || streaming}
              className="p-2 bg-accent rounded-lg text-white hover:bg-accent-hover
                transition-colors disabled:opacity-40 flex-shrink-0">
              <Send size={15}/>
            </button>
          </div>
          <p className="text-xs text-muted text-center mt-2">
            Enter para enviar · Shift+Enter para nova linha
          </p>
        </div>
      </div>

      {/* Fechar menu ao clicar fora */}
      {menuSid && <div className="fixed inset-0 z-40" onClick={() => setMenuSid(null)}/>}
    </div>
  );
}
