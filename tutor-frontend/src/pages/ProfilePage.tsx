import React, { useState } from "react";
import { apiPost } from "../api";

const LEVELS = [
  { id: "iniciante",     label: "Iniciante",     desc: "Estou começando agora" },
  { id: "intermediario", label: "Intermediário",  desc: "Já tenho alguma experiência" },
  { id: "avancado",      label: "Avançado",       desc: "Tenho bastante experiência" },
];
const PURPOSES = [
  { id: "academico",    label: "Atividades Acadêmicas",   desc: "Faculdade, TCC, provas" },
  { id: "profissional", label: "Atividades Profissionais", desc: "Trabalho, projetos" },
  { id: "hobby",        label: "Atividades de Passatempo", desc: "Aprendizado por interesse" },
];

interface Props { onSaved: () => void; }

export default function ProfilePage({ onSaved }: Props) {
  const [level, setLevel] = useState("");
  const [purposes, setPurposes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const togglePurpose = (id: string) =>
    setPurposes(p => p.includes(id) ? p.filter(x=>x!==id) : [...p,id]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!level) { setError("Selecione seu nível."); return; }
    if (!purposes.length) { setError("Selecione pelo menos um propósito."); return; }
    setLoading(true); setError("");
    const r = await apiPost("/student/onboarding", { level, purpose: purposes });
    if (r.ok) { setSuccess(true); setTimeout(onSaved, 1500); }
    else setError("Erro ao salvar. Tente novamente.");
    setLoading(false);
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-lg mx-auto">
        <h1 className="text-xl font-bold text-text mb-1">⚙️ Configurar Perfil</h1>
        <p className="text-muted text-sm mb-6">Atualize suas preferências para personalizar o tutor</p>

        <form onSubmit={handleSave} className="space-y-6">
          <div>
            <h2 className="font-semibold text-text mb-3">Nível de conhecimento em programação</h2>
            <div className="space-y-2">
              {LEVELS.map(l => (
                <label key={l.id} onClick={() => setLevel(l.id)}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all
                    ${level===l.id ? "border-accent bg-accent/10" : "border-border hover:border-soft hover:bg-panel"}`}>
                  <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0
                    ${level===l.id ? "border-accent bg-accent" : "border-muted"}`}/>
                  <div>
                    <span className="font-medium text-text">{l.label}</span>
                    <span className="text-muted text-sm ml-2">— {l.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div>
            <h2 className="font-semibold text-text mb-1">Propósito de Uso do TutorAndCoder</h2>
            <p className="text-muted text-xs mb-3">Mais de uma opção selecionável</p>
            <div className="space-y-2">
              {PURPOSES.map(p => (
                <label key={p.id} onClick={() => togglePurpose(p.id)}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all
                    ${purposes.includes(p.id) ? "border-accent bg-accent/10" : "border-border hover:border-soft hover:bg-panel"}`}>
                  <div className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center
                    ${purposes.includes(p.id) ? "border-accent bg-accent" : "border-muted"}`}>
                    {purposes.includes(p.id) && <span className="text-white text-xs">✓</span>}
                  </div>
                  <div>
                    <span className="font-medium text-text">{p.label}</span>
                    <span className="text-muted text-sm ml-2">— {p.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {error && <p className="text-danger text-sm">{error}</p>}
          {success && <p className="text-green-400 text-sm">✓ Perfil atualizado!</p>}

          <div className="flex gap-3">
            <button type="submit" disabled={loading}
              className="flex-1 bg-accent hover:bg-accent-hover text-white font-medium py-2.5
                rounded-lg transition-colors disabled:opacity-50">
              {loading ? "Salvando..." : "Salvar perfil"}
            </button>
            <button type="button" onClick={onSaved}
              className="px-4 py-2.5 bg-accent/15 text-accent font-medium rounded-lg
                hover:bg-accent/25 transition-colors">
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
