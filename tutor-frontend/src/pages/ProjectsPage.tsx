import React, { useState, useEffect, useRef } from "react";
import { apiGet, apiPost, apiDelete } from "../api";
import {
  Plus, Search, Download, Trash2, Edit2, FolderOpen,
  FileText, Save, X, Check, MoreVertical,
  Loader, ArrowLeft, Wand2, Upload, FilePlus
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Tree { [project: string]: string[] }
interface ProjectMeta { name: string; files: string[]; }

// ── Helpers ─────────────────────────────────────────────────────────────────

function timeAgo(files: string[]): string {
  const visible = files.filter(f => f !== ".projectinfo");
  return visible.length === 1 ? "1 arquivo" : `${visible.length} arquivos`;
}

// ── New Project Modal ────────────────────────────────────────────────────────

function NewProjectModal({ onClose, onCreated }: {
  onClose: () => void;
  onCreated: (name: string) => void;
}) {
  const [step, setStep] = useState<"choose" | "blank" | "ai" | "import">("choose");
  const [projectName, setProjectName] = useState("");
  const [aiDesc, setAiDesc] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // Progresso em tempo real da geração via IA
  const [aiStatus, setAiStatus] = useState("");
  const [aiCreatedFiles, setAiCreatedFiles] = useState<string[]>([]);
  const uploadRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  async function createBlank() {
    if (!projectName.trim()) { setError("Digite um nome para o projeto."); return; }
    setLoading(true); setError("");
    const folder = projectName.trim().replace(/\s+/g,"_");
    // Cria um marcador oculto para a pasta existir sem ter um arquivo visível
    const path = `${folder}/.projectinfo`;
    const r = await apiPost("/files/write", { path, content: "" });
    if (r.ok) { onCreated(folder); }
    else setError("Erro ao criar projeto.");
    setLoading(false);
  }

  async function createWithAI() {
    if (!aiDesc.trim()) { setError("Descreva o projeto."); return; }
    setLoading(true); setError("");
    setAiStatus("");
    setAiCreatedFiles([]);

    let detectedFolder = "";
    let finished = false;
    let hadError = false;

    try {
      const r = await apiPost("/projects/generate", { description: aiDesc });
      if (!r.body) throw new Error("Sem resposta do servidor.");

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
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") continue;

          try {
            const data = JSON.parse(payload);

            if (data.type === "status" && data.message) {
              setAiStatus(data.message);
            } else if (data.type === "file_created" && data.path) {
              setAiCreatedFiles(prev => [...prev, data.path]);
              setAiStatus(`Arquivo criado: ${data.path}`);
              // Detecta a pasta do projeto a partir do primeiro arquivo criado
              if (!detectedFolder && data.path.includes("/")) {
                detectedFolder = data.path.split("/")[0];
              }
            } else if (data.type === "error" && data.message) {
              setError(data.message);
              hadError = true;
              finished = true;
            } else if (data.type === "done") {
              setAiStatus("Projeto criado com sucesso!");
              finished = true;
            }
          } catch {
            // linha não-JSON, ignora
          }
        }
      }
    } catch (e) {
      setError(`Erro ao gerar projeto: ${e}`);
      hadError = true;
      finished = true;
    }

    setLoading(false);

    if (!hadError && finished) {
      // Pequena pausa para o usuário ver a mensagem de sucesso antes de fechar
      setTimeout(() => onCreated(detectedFolder), 900);
    }
  }

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files; if (!files || files.length === 0) return;
    setLoading(true);
    const firstName = files[0].name.replace(/\.[^.]+$/, "");
    const folderName = projectName.trim().replace(/\s+/g, "_") || firstName;
    for (const file of Array.from(files)) {
      const text = await file.text().catch(() => "");
      await apiPost("/files/write", { path: `${folderName}/${file.name}`, content: text });
    }
    onCreated(folderName);
    setLoading(false);
  }

  async function handleImportFolder(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files; if (!files || files.length === 0) return;
    setLoading(true);
    // webkitRelativePath: "pasta/subpasta/arquivo.ext"
    const rootFolder = (files[0] as any).webkitRelativePath?.split("/")[0] || projectName.trim() || "projeto";
    const folderName = (projectName.trim().replace(/\s+/g, "_")) || rootFolder;
    for (const file of Array.from(files)) {
      const relativePath = (file as any).webkitRelativePath || file.name;
      // Mantém estrutura de subpastas dentro do projeto
      const pathParts = relativePath.split("/").slice(1).join("/"); // remove root folder name
      const finalPath = `${folderName}/${pathParts || file.name}`;
      const text = await file.text().catch(() => "");
      await apiPost("/files/write", { path: finalPath, content: text });
    }
    onCreated(folderName);
    setLoading(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            {step !== "choose" && (
              <button onClick={() => { setStep("choose"); setError(""); }}
                className="text-muted hover:text-text mr-1 transition-colors">
                <ArrowLeft size={16}/>
              </button>
            )}
            <h2 className="font-semibold text-text">
              {step === "choose" && "Novo Projeto"}
              {step === "blank"  && "Criar Projeto em Branco"}
              {step === "ai"     && "Criar Projeto com IA"}
              {step === "import" && "Importar Projeto"}
            </h2>
          </div>
          <button onClick={onClose} className="text-muted hover:text-text transition-colors">
            <X size={18}/>
          </button>
        </div>

        {/* Choose */}
        {step === "choose" && (
          <div className="p-4 space-y-2">
            <button onClick={() => setStep("blank")}
              className="w-full flex items-center gap-4 p-4 rounded-xl border border-border
                hover:border-accent hover:bg-accent/5 transition-all text-left group">
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center
                group-hover:bg-accent/20 transition-colors">
                <FilePlus size={20} className="text-accent"/>
              </div>
              <div>
                <p className="font-medium text-text">Criar Projeto em Branco</p>
                <p className="text-xs text-muted mt-0.5">Cria um projeto vazio com um arquivo inicial</p>
              </div>
            </button>

            <button onClick={() => setStep("ai")}
              className="w-full flex items-center gap-4 p-4 rounded-xl border border-border
                hover:border-accent hover:bg-accent/5 transition-all text-left group">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center
                group-hover:bg-purple-500/20 transition-colors">
                <Wand2 size={20} className="text-purple-400"/>
              </div>
              <div>
                <p className="font-medium text-text">Criar Projeto com IA</p>
                <p className="text-xs text-muted mt-0.5">Descreva o projeto e a IA gera os arquivos</p>
              </div>
            </button>

            <button onClick={() => setStep("import")}
              className="w-full flex items-center gap-4 p-4 rounded-xl border border-border
                hover:border-accent hover:bg-accent/5 transition-all text-left group">
              <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center
                group-hover:bg-green-500/20 transition-colors">
                <Upload size={20} className="text-green-400"/>
              </div>
              <div>
                <p className="font-medium text-text">Importar Projeto</p>
                <p className="text-xs text-muted mt-0.5">Importe arquivos do seu computador</p>
              </div>
            </button>
          </div>
        )}

        {/* Blank project */}
        {step === "blank" && (
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm text-soft mb-1.5">Nome do projeto</label>
              <input value={projectName} onChange={e => setProjectName(e.target.value)}
                autoFocus placeholder="meu_projeto"
                onKeyDown={e => e.key === "Enter" && createBlank()}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                  focus:outline-none focus:border-accent transition-colors"/>
            </div>
            {error && <p className="text-danger text-sm">{error}</p>}
            <button onClick={createBlank} disabled={loading}
              className="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2.5
                rounded-lg transition-colors disabled:opacity-50">
              {loading ? "Criando..." : "Criar Projeto"}
            </button>
          </div>
        )}

        {/* AI project */}
        {step === "ai" && (
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm text-soft mb-1.5">Descreva o projeto</label>
              <textarea value={aiDesc} onChange={e => setAiDesc(e.target.value)}
                autoFocus rows={4} disabled={loading}
                placeholder="Ex: Projeto Python de calculadora com interface de terminal, incluindo main.py, calculadora.py e README.md"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                  focus:outline-none focus:border-accent transition-colors resize-none disabled:opacity-60"/>
            </div>

            {/* Progresso ao vivo da geração — só aparece quando há status real */}
            {loading && aiStatus && (
              <div className="bg-panel border border-border rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-2 text-sm text-soft">
                  <Loader size={14} className="animate-spin text-purple-400 flex-shrink-0"/>
                  <span>{aiStatus}</span>
                </div>
                {aiCreatedFiles.length > 0 && (
                  <div className="pl-6 space-y-1">
                    {aiCreatedFiles.map(f => (
                      <div key={f} className="flex items-center gap-1.5 text-xs text-green-400">
                        <Check size={11} className="flex-shrink-0"/>
                        <span className="font-mono">{f}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-danger text-sm">{error}</p>}

            <button onClick={createWithAI} disabled={loading}
              className="w-full bg-purple-600 hover:bg-purple-700 text-white font-medium py-2.5
                rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
              {loading ? <><Loader size={16} className="animate-spin"/> Gerando...</> : <><Wand2 size={16}/> Gerar com IA</>}
            </button>
          </div>
        )}

        {/* Import */}
        {step === "import" && (
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm text-soft mb-1.5">Nome do projeto (opcional)</label>
              <input value={projectName} onChange={e => setProjectName(e.target.value)}
                placeholder="nome_do_projeto"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                  focus:outline-none focus:border-accent transition-colors"/>
            </div>

            <input ref={uploadRef} type="file" multiple className="hidden" onChange={handleImportFile}/>
            <input ref={folderRef} type="file" className="hidden" onChange={handleImportFolder}
              {...{ webkitdirectory: "", mozdirectory: "" } as any} multiple/>

            <div className="grid grid-cols-2 gap-3">
              <button onClick={() => uploadRef.current?.click()} disabled={loading}
                className="flex flex-col items-center justify-center gap-2 border-2 border-dashed
                  border-border hover:border-accent rounded-xl py-6 text-muted hover:text-text
                  transition-all disabled:opacity-50">
                <FileText size={22}/>
                <span className="text-xs font-medium mt-1">Arquivo(s)</span>
                <span className="text-xs text-muted">Selecionar arquivos</span>
              </button>

              <button onClick={() => folderRef.current?.click()} disabled={loading}
                className="flex flex-col items-center justify-center gap-2 border-2 border-dashed
                  border-border hover:border-accent rounded-xl py-6 text-muted hover:text-text
                  transition-all disabled:opacity-50">
                <FolderOpen size={22}/>
                <span className="text-xs font-medium mt-1">Pasta inteira</span>
                <span className="text-xs text-muted">Selecionar pasta</span>
              </button>
            </div>

            {loading && (
              <div className="flex items-center justify-center gap-2 text-sm text-muted py-2">
                <Loader size={14} className="animate-spin"/> Importando arquivos...
              </div>
            )}
            <p className="text-xs text-muted text-center">Suporta qualquer tipo de arquivo ou pasta</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Project List View ────────────────────────────────────────────────────────

function ProjectListView({ projects, onOpen, onRename, onDelete, onDownload, search, setSearch, onNewProject }: {
  projects: ProjectMeta[];
  onOpen: (name: string) => void;
  onRename: (name: string) => void;
  onDelete: (name: string) => void;
  onDownload: (name: string) => void;
  onNewProject: () => void;
  search: string;
  setSearch: (s: string) => void;
}) {
  const filtered = projects.filter(p =>
    !search || p.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      {/* Sidebar esquerda estilo Overleaf */}
      <div className="w-56 flex-shrink-0 border-r border-border bg-surface flex flex-col py-6 px-4 gap-3">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/10 text-white text-sm font-medium">
            <FolderOpen size={15}/> Projetos
          </div>
        </div>
        <button onClick={onNewProject}
          className="w-full flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover
            text-white font-semibold py-2.5 rounded-lg transition-colors text-sm">
          <Plus size={16}/> Novo Projeto
        </button>
      </div>

      {/* Área principal */}
      <div className="flex-1 overflow-y-auto p-8">
        <h2 className="text-lg font-semibold text-text mb-5">Todos os projetos</h2>

        {/* Search */}
        <div className="relative mb-5">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"/>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Buscar projetos..."
            className="w-full bg-surface border border-border rounded-lg pl-9 pr-4 py-2.5
              text-sm text-text focus:outline-none focus:border-accent transition-colors"/>
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-20">
            <FolderOpen size={48} className="text-border mx-auto mb-4"/>
            <h3 className="text-text font-medium mb-1">
              {search ? "Nenhum projeto encontrado" : "Nenhum projeto"}
            </h3>
            <p className="text-muted text-sm mt-1">
              {search ? "Tente outro termo de busca" : "Clique em Novo Projeto para começar"}
            </p>
          </div>
        ) : (
          <div className="border border-border rounded-xl overflow-hidden">
            <div className="grid grid-cols-[1fr_120px_120px] px-4 py-2.5 border-b border-border bg-panel">
              <span className="text-xs font-semibold text-muted uppercase tracking-wider">Título</span>
              <span className="text-xs font-semibold text-muted uppercase tracking-wider">Arquivos</span>
              <span className="text-xs font-semibold text-muted uppercase tracking-wider text-right pr-2">Ações</span>
            </div>
            {filtered.map((p, i) => (
              <div key={p.name}
                className={`grid grid-cols-[1fr_120px_120px] items-center px-4 py-3.5
                  hover:bg-surface/60 transition-colors
                  ${i < filtered.length - 1 ? "border-b border-border/40" : ""}`}>
                <button onClick={() => onOpen(p.name)}
                  className="flex items-center gap-2.5 text-left min-w-0">
                  <FolderOpen size={16} className="text-accent/60 flex-shrink-0"/>
                  <span className="text-text hover:underline text-sm font-medium truncate">
                    {p.name}
                  </span>
                </button>
                <span className="text-sm text-muted">{timeAgo(p.files)}</span>
                <div className="flex items-center justify-end gap-0.5">
                  <button onClick={() => onDownload(p.name)} title="Baixar"
                    className="p-1.5 text-muted hover:text-text rounded-lg transition-colors">
                    <Download size={14}/>
                  </button>
                  <button onClick={() => onRename(p.name)} title="Renomear"
                    className="p-1.5 text-muted hover:text-text rounded-lg transition-colors">
                    <Edit2 size={14}/>
                  </button>
                  <button onClick={() => onDelete(p.name)} title="Excluir"
                    className="p-1.5 text-muted hover:text-danger rounded-lg transition-colors">
                    <Trash2 size={14}/>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Project Editor View ──────────────────────────────────────────────────────

function ProjectEditorView({ projectName, files, onBack, onTreeRefresh, analysisMap, setAnalysisMap }: {
  projectName: string;
  files: string[];
  onBack: () => void;
  onTreeRefresh: () => void;
  analysisMap: Record<string, string>;
  setAnalysisMap: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}) {
  // Garante que files é sempre um array, e oculta o marcador .projectinfo
  const safeFiles = (Array.isArray(files) ? files : Object.values(files || {}) as string[])
    .filter(f => f !== ".projectinfo");
  const [activeFile, setActiveFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [originalContent, setOriginalContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(false);
  // Chave da análise atualmente exibida no painel — muda ao trocar de arquivo
  // ou ao analisar o projeto inteiro. O conteúdo em si vive em analysisMap,
  // que pertence ao componente pai e por isso sobrevive à navegação.
  const [analysisKey, setAnalysisKey] = useState<string | null>(null);
  const [analyzingKey, setAnalyzingKey] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<string | null>(null);
  const [newFileName, setNewFileName] = useState("");
  const [showNewFile, setShowNewFile] = useState(false);
  const [renamingFile, setRenamingFile] = useState<string | null>(null);
  const [menuFile, setMenuFile] = useState<string | null>(null);
  const [renameFileVal, setRenameFileVal] = useState("");
  const uploadRef = useRef<HTMLInputElement>(null);

  const projectKey = `${projectName}::__project__`;
  const analyzing = analyzingKey !== null && analyzingKey === analysisKey;
  const analysis = analysisKey ? (analysisMap[analysisKey] ?? null) : null;
  const displayName = projectName === "_root" ? "Outros Arquivos" : projectName;

  // Atualiza o título da aba do navegador para o nome do projeto
  useEffect(() => {
    const previousTitle = document.title;
    document.title = `${displayName} — TutorAndCoder`;
    return () => { document.title = previousTitle; };
  }, [displayName]);

  async function openFile(fname: string) {
    const path = projectName === "_root" ? fname : `${projectName}/${fname}`;
    setLoading(true);
    const r = await apiPost("/files/read", { path });
    if (r.ok) {
      const d = await r.json();
      const c = d.message || "";
      setContent(c); setOriginalContent(c);
      setActiveFile(fname); setDirty(false);
      // A análise exibida passa a ser a do arquivo recém-aberto
      // (mostra a análise salva desse arquivo, se houver, ou nada)
      setAnalysisKey(`${projectName}/${fname}`);
    }
    setLoading(false);
  }

  async function saveFile() {
    if (!activeFile) return;
    const path = projectName === "_root" ? activeFile : `${projectName}/${activeFile}`;
    await apiPost("/files/write", { path, content });
    setOriginalContent(content); setDirty(false);
  }

  async function deleteFile(fname: string) {
    if (!window.confirm(`Excluir ${fname}?`)) return;
    const path = projectName === "_root" ? fname : `${projectName}/${fname}`;
    await apiDelete(`/files/delete?path=${encodeURIComponent(path)}`);
    // Remove também qualquer análise salva para esse arquivo específico
    setAnalysisMap(prev => {
      const copy = { ...prev };
      delete copy[path];
      return copy;
    });
    if (activeFile === fname) {
      setActiveFile(null); setContent(""); setAnalysisKey(null);
    }
    onTreeRefresh();
  }

  async function renameFile(oldName: string) {
    if (!renameFileVal.trim() || renameFileVal === oldName) { setRenamingFile(null); return; }
    const newName = renameFileVal.trim();
    const oldPath = projectName === "_root" ? oldName : `${projectName}/${oldName}`;
    const newPath = projectName === "_root" ? newName : `${projectName}/${newName}`;

    const r = await apiPost("/files/read", { path: oldPath });
    if (r.ok) {
      const d = await r.json();
      await apiPost("/files/write", { path: newPath, content: d.message || "" });
      await apiDelete(`/files/delete?path=${encodeURIComponent(oldPath)}`);
      // Transfere a análise salva do caminho antigo para o novo, se houver
      setAnalysisMap(prev => {
        if (!(oldPath in prev)) return prev;
        const copy = { ...prev };
        copy[newPath] = copy[oldPath];
        delete copy[oldPath];
        return copy;
      });
      if (activeFile === oldName) {
        setActiveFile(newName);
        setAnalysisKey(newPath);
      }
    }
    setRenamingFile(null);
    onTreeRefresh();
  }

  async function createFile() {
    if (!newFileName.trim()) return;
    const path = projectName === "_root" ? newFileName.trim() : `${projectName}/${newFileName.trim()}`;
    await apiPost("/files/write", { path, content: "" });
    // Remove o marcador .projectinfo agora que existe um arquivo real
    if (projectName !== "_root" && safeFiles.length === 0) {
      await apiDelete(`/files/delete?path=${encodeURIComponent(`${projectName}/.projectinfo`)}`);
    }
    setShowNewFile(false); setNewFileName("");
    onTreeRefresh();
    openFile(newFileName.trim());
  }

  // Consome resposta SSE (Server-Sent Events) do backend, streaming linha a linha
  async function consumeSSE(response: Response, onChunk: (text: string) => void) {
    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") return;
        try {
          const data = JSON.parse(payload);
          if (data.type === "chunk" && data.content) onChunk(data.content);
          else if (data.type === "done" && data.message) onChunk(data.message);
          else if (data.type === "error" && data.message) onChunk(`⚠️ ${data.message}`);
          else if (data.type === "status" && data.message) {
            // Mostra status de progresso enquanto não há conteúdo ainda
            setAnalysisStatus(data.message);
          }
        } catch {
          // Ignora linhas que não são JSON válido
        }
      }
    }
  }

  async function analyzeFile() {
    if (!activeFile) return;
    const key = `${projectName}/${activeFile}`;
    const path = projectName === "_root" ? activeFile : key;
    setAnalysisKey(key);
    setAnalyzingKey(key);
    setAnalysisMap(prev => ({ ...prev, [key]: "" }));
    setAnalysisStatus("Iniciando análise...");
    try {
      const r = await apiPost("/analysis/file", { path });
      let accumulated = "";
      await consumeSSE(r, (text) => {
        accumulated += text;
        setAnalysisMap(prev => ({ ...prev, [key]: accumulated }));
        setAnalysisStatus(null);
      });
    } catch (e) {
      setAnalysisMap(prev => ({ ...prev, [key]: `Erro ao analisar arquivo: ${e}` }));
    }
    setAnalyzingKey(null);
    setAnalysisStatus(null);
  }

  async function analyzeProject() {
    const key = projectKey;
    setAnalysisKey(key);
    setAnalyzingKey(key);
    setAnalysisMap(prev => ({ ...prev, [key]: "" }));
    setAnalysisStatus("Iniciando análise...");
    try {
      const r = await apiPost("/analysis/project", { project: projectName });
      let accumulated = "";
      await consumeSSE(r, (text) => {
        accumulated += text;
        setAnalysisMap(prev => ({ ...prev, [key]: accumulated }));
        setAnalysisStatus(null);
      });
    } catch (e) {
      setAnalysisMap(prev => ({ ...prev, [key]: `Erro ao analisar projeto: ${e}` }));
    }
    setAnalyzingKey(null);
    setAnalysisStatus(null);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    const text = await file.text();
    const path = projectName === "_root" ? file.name : `${projectName}/${file.name}`;
    await apiPost("/files/write", { path, content: text });
    if (projectName !== "_root" && safeFiles.length === 0) {
      await apiDelete(`/files/delete?path=${encodeURIComponent(`${projectName}/.projectinfo`)}`);
    }
    onTreeRefresh();
    openFile(file.name);
    e.target.value = "";
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Top bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-surface">
        <button onClick={onBack}
          className="text-muted hover:text-text transition-colors">
          <ArrowLeft size={16}/>
        </button>
        <button onClick={onBack}
          className="text-muted hover:text-text transition-colors text-sm">
          Voltar para Lista Projetos
        </button>
        <span className="text-border">/</span>
        <span className="font-semibold text-text text-sm">{displayName}</span>
        {projectName !== "_root" && (
          <button onClick={analyzeProject} disabled={analyzing}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-accent/15 text-accent
              rounded-lg hover:bg-accent/25 transition-colors disabled:opacity-60">
            {analyzingKey === projectKey
              ? <><Loader size={11} className="animate-spin"/> Análise</>
              : "Analisar Projeto"}
          </button>
        )}
        <div className="ml-auto flex items-center gap-2">
          {dirty && (
            <button onClick={saveFile}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-accent
                hover:bg-accent-hover text-white rounded-lg transition-colors">
              <Save size={12}/> Salvar
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* File tree */}
        <div className="w-56 flex-shrink-0 border-r border-border bg-surface flex flex-col">
          {/* Nome do projeto — clicável, volta para a tela "Selecione um arquivo" */}
          <button onClick={() => setActiveFile(null)}
            className="text-left px-3 pt-3 pb-1 text-sm font-semibold text-text
              hover:text-accent transition-colors truncate">
            {displayName}
          </button>
          <div className="px-3 py-2 border-b border-border flex items-center justify-between">
            <span className="text-xs font-semibold text-muted uppercase tracking-wider">Arquivos</span>
            <div className="flex gap-1">
              <button onClick={() => setShowNewFile(!showNewFile)} title="Novo arquivo"
                className="p-1.5 bg-accent/15 text-accent hover:bg-accent/25 rounded-md
                  transition-colors"><Plus size={14}/></button>
              <button onClick={() => uploadRef.current?.click()} title="Importar arquivo"
                className="p-1.5 bg-accent/15 text-accent hover:bg-accent/25 rounded-md
                  transition-colors"><Upload size={14}/></button>
            </div>
          </div>
          <input ref={uploadRef} type="file" className="hidden" onChange={handleUpload}/>

          {showNewFile && (
            <div className="p-2 border-b border-border flex gap-1">
              <input value={newFileName} onChange={e => setNewFileName(e.target.value)} autoFocus
                placeholder="arquivo.py"
                onKeyDown={e => { if (e.key === "Enter") createFile(); if (e.key === "Escape") setShowNewFile(false); }}
                className="flex-1 bg-bg border border-accent rounded px-2 py-1 text-xs text-text focus:outline-none"/>
              <button onClick={createFile} className="p-1 bg-accent rounded text-white"><Check size={12}/></button>
            </div>
          )}

          <div className="flex-1 overflow-y-auto py-1">
            {safeFiles.map(fname => (
              <div key={fname}>
                {renamingFile === fname ? (
                  <div className="flex items-center gap-1 px-2 py-1 mx-1">
                    <input value={renameFileVal} onChange={e => setRenameFileVal(e.target.value)}
                      autoFocus
                      onKeyDown={e => {
                        if (e.key === "Enter") renameFile(fname);
                        if (e.key === "Escape") setRenamingFile(null);
                      }}
                      className="flex-1 bg-bg border border-accent rounded px-2 py-1 text-xs
                        text-text focus:outline-none min-w-0"/>
                    <button onClick={() => renameFile(fname)}
                      className="p-1 bg-accent rounded text-white flex-shrink-0">
                      <Check size={11}/>
                    </button>
                    <button onClick={() => setRenamingFile(null)}
                      className="p-1 text-muted hover:text-text flex-shrink-0">
                      <X size={11}/>
                    </button>
                  </div>
                ) : (
                  <div className={`relative group flex items-center gap-2 px-3 py-2 cursor-pointer rounded mx-1
                      transition-colors
                      ${activeFile === fname ? "bg-accent/10 text-accent" : "text-muted hover:text-text hover:bg-panel"}`}>
                    <FileText size={12} className="flex-shrink-0"/>
                    <span className="text-xs flex-1 truncate" onClick={() => openFile(fname)}>{fname}</span>

                    {/* Botão de mais ações — sempre visível */}
                    <button onClick={(e) => { e.stopPropagation(); setMenuFile(menuFile===fname?null:fname); }}
                      className={`p-1 rounded transition-colors flex-shrink-0
                        text-muted hover:text-text
                        ${menuFile===fname ? "text-text bg-panel" : ""}`}>
                      <MoreVertical size={12}/>
                    </button>

                    {/* Menu popup */}
                    {menuFile===fname && (
                      <div className="absolute right-0 top-full mt-1 w-40 bg-panel border border-border
                        rounded-lg shadow-xl z-50 overflow-hidden">
                        <button onClick={() => { setRenamingFile(fname); setRenameFileVal(fname); setMenuFile(null); }}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-text
                            hover:bg-surface transition-colors">
                          <Edit2 size={12} className="text-muted"/> Renomear
                        </button>
                        <button onClick={() => { deleteFile(fname); setMenuFile(null); }}
                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-danger
                            hover:bg-danger/10 transition-colors">
                          <Trash2 size={12}/> Excluir
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Fecha o menu de arquivo ao clicar fora */}
          {menuFile && <div className="fixed inset-0 z-40" onClick={() => setMenuFile(null)}/>}
        </div>

        {/* Editor + Analysis */}
        <div className="flex flex-1 min-w-0">
          {/* Editor */}
          <div className={`flex flex-col ${analysis ? "w-1/2" : "w-full"} transition-all`}>
            {activeFile ? (
              loading ? (
                <div className="flex-1 flex items-center justify-center">
                  <Loader size={20} className="animate-spin text-accent"/>
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-panel">
                    <FileText size={13} className="text-muted"/>
                    <span className="text-sm text-text font-mono">{activeFile}</span>
                    {dirty && <span className="w-1.5 h-1.5 rounded-full bg-accent ml-1"/>}
                    <button onClick={analyzeFile} disabled={analyzing}
                      className="flex items-center gap-1.5 text-xs px-3 py-1 ml-2 bg-accent/15 text-accent
                        rounded-lg hover:bg-accent/25 transition-colors disabled:opacity-60">
                      {analyzingKey === `${projectName}/${activeFile}`
                        ? <><Loader size={11} className="animate-spin"/> Análise</>
                        : "Analisar Arquivo"}
                    </button>
                  </div>
                  <textarea value={content}
                    onChange={e => { setContent(e.target.value); setDirty(e.target.value !== originalContent); }}
                    className="flex-1 bg-bg text-text font-mono text-sm p-4 resize-none
                      focus:outline-none border-none leading-relaxed"
                    spellCheck={false}/>
                </>
              )
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                <FileText size={40} className="text-border mb-3"/>
                <p className="text-text font-medium">Selecione um arquivo</p>
                <p className="text-muted text-sm mt-1">Clique em um arquivo na lista à esquerda</p>
              </div>
            )}
          </div>

          {/* Analysis panel — mostra enquanto analisa OU quando há conteúdo */}
          {(analyzing || analysis) && (
            <div className="w-1/2 border-l border-border flex flex-col">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-surface">
                <span className="text-sm font-medium text-text">📋 Análise</span>
                <button onClick={() => {
                    // Exclui a análise permanentemente apenas quando o usuário fecha
                    if (analysisKey) {
                      setAnalysisMap(prev => {
                        const copy = { ...prev };
                        delete copy[analysisKey];
                        return copy;
                      });
                    }
                    setAnalysisStatus(null);
                  }}
                  className="text-muted hover:text-text"><X size={14}/></button>
              </div>
              <div className="flex-1 overflow-y-auto p-4 prose">
                {analysisStatus && (
                  <div className="flex items-center gap-2 text-muted text-sm mb-3">
                    <Loader size={14} className="animate-spin"/> {analysisStatus}
                  </div>
                )}
                {analysis && <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis}</ReactMarkdown>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function ProjectsPage() {
  const [tree, setTree] = useState<Tree>({});
  const [openProject, setOpenProject] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [search, setSearch] = useState("");
  const [renamingProject, setRenamingProject] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState("");
  // Guarda o resultado de análise por arquivo/projeto — persiste ao navegar
  // entre a lista de projetos e o editor, pois vive neste componente pai.
  const [analysisMap, setAnalysisMap] = useState<Record<string, string>>({});

  useEffect(() => { loadTree(); }, []);

  async function loadTree() {
    try {
      const r = await apiGet("/files/tree");
      if (r.ok) {
        const d = await r.json();
        setTree(d.tree || {});
      }
    } catch (e) {
      console.error("Erro ao carregar árvore:", e);
    }
  }

  async function deleteProject(name: string) {
    if (!window.confirm(`Excluir o projeto "${name}" e todos os seus arquivos?`)) return;
    const rawFiles = tree[name] || [];
    const files = Array.isArray(rawFiles) ? rawFiles : Object.values(rawFiles) as string[];
    for (const f of files) {
      await apiDelete(`/files/delete?path=${encodeURIComponent(`${name}/${f}`)}`);
    }
    loadTree();
  }

  async function downloadProject(name: string) {
    // Creates a simple text manifest since we can't zip in browser easily
    const rawFiles3 = tree[name] || [];
    const files = (Array.isArray(rawFiles3) ? rawFiles3 : Object.values(rawFiles3) as string[])
      .filter(f => f !== ".projectinfo");
    const contents: string[] = [`# Projeto: ${name}\n# Arquivos:\n`];
    for (const f of files) {
      const r = await apiPost("/files/read", { path: `${name}/${f}` });
      if (r.ok) {
        const d = await r.json();
        contents.push(`\n${"=".repeat(60)}\n# ${f}\n${"=".repeat(60)}\n${d.message || ""}`);
      }
    }
    const blob = new Blob([contents.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${name}.txt`; a.click();
    URL.revokeObjectURL(url);
  }

  async function renameProject(oldName: string) {
    if (!renameVal.trim() || renameVal === oldName) { setRenamingProject(null); return; }
    const newName = renameVal.trim().replace(/\s+/g,"_");
    const files = tree[oldName] || [];
    for (const f of files) {
      const r = await apiPost("/files/read", { path: `${oldName}/${f}` });
      if (r.ok) {
        const d = await r.json();
        await apiPost("/files/write", { path: `${newName}/${f}`, content: d.message || "" });
        await apiDelete(`/files/delete?path=${encodeURIComponent(`${oldName}/${f}`)}`);
      }
    }
    setRenamingProject(null);
    loadTree();
  }

  // Build project list (exclude _root loose files from main view)
  const projects: ProjectMeta[] = Object.entries(tree)
    .filter(([k]) => k !== "_root" && k !== "")
    .map(([name, files]) => ({ name, files: files as string[] }));

  // Debug: log tree on change
  React.useEffect(() => {
    console.log("[Projects] tree:", tree);
    console.log("[Projects] projects:", Object.keys(tree));
  }, [tree]);

  const rawCurrentFiles = openProject ? (tree[openProject] || []) : [];
  const currentFiles = Array.isArray(rawCurrentFiles)
    ? rawCurrentFiles
    : Object.values(rawCurrentFiles) as string[];

  return (
    <div className="flex flex-col flex-1 h-screen overflow-hidden">
      {/* Content */}
      {openProject ? (
        <ProjectEditorView
          projectName={openProject}
          files={currentFiles}
          onBack={async () => {
            setOpenProject(null);
            await loadTree();
          }}
          onTreeRefresh={loadTree}
          analysisMap={analysisMap}
          setAnalysisMap={setAnalysisMap}
        />
      ) : (
        <>
          {/* Rename inline */}
          {renamingProject && (
            <div className="px-8 py-3 bg-accent/5 border-b border-accent/20 flex items-center gap-3">
              <span className="text-sm text-soft">Renomear <b>{renamingProject}</b> para:</span>
              <input value={renameVal} onChange={e => setRenameVal(e.target.value)} autoFocus
                onKeyDown={e => { if (e.key === "Enter") renameProject(renamingProject); if (e.key === "Escape") setRenamingProject(null); }}
                className="bg-bg border border-accent rounded px-3 py-1.5 text-sm text-text
                  focus:outline-none w-48"/>
              <button onClick={() => renameProject(renamingProject)}
                className="px-3 py-1.5 bg-accent text-white text-sm rounded hover:bg-accent-hover">
                Salvar
              </button>
              <button onClick={() => setRenamingProject(null)}
                className="text-muted hover:text-text text-sm">Cancelar</button>
            </div>
          )}

          <ProjectListView
            projects={projects}
            search={search}
            setSearch={setSearch}
            onOpen={name => { setOpenProject(name); }}
            onRename={name => { setRenamingProject(name); setRenameVal(name); }}
            onDelete={deleteProject}
            onDownload={downloadProject}
            onNewProject={() => setShowModal(true)}
          />
        </>
      )}

      {/* Modal */}
      {showModal && (
        <NewProjectModal
          onClose={() => setShowModal(false)}
          onCreated={name => { setShowModal(false); loadTree(); if (name) setOpenProject(name); }}
        />
      )}
    </div>
  );
}
