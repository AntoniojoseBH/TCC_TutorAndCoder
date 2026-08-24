import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
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

export default function OnboardingPage() {
  const { user, setOnboardingDone } = useAuth();
  const [level, setLevel] = useState("");
  const [purposes, setPurposes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const togglePurpose = (id: string) =>
    setPurposes(p => p.includes(id) ? p.filter(x=>x!==id) : [...p,id]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!level) { setError("Selecione seu nível."); return; }
    if (purposes.length === 0) { setError("Selecione pelo menos um propósito."); return; }
    setLoading(true); setError("");
    const r = await apiPost("/student/onboarding", { level, purpose: purposes });
    if (r.ok) { setOnboardingDone(true); }
    else setError("Erro ao salvar perfil. Tente novamente.");
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <div className="text-4xl mb-2">🎓</div>
          <h1 className="text-2xl font-bold text-text">Bem-vindo, {user?.name}!</h1>
          <p className="text-muted text-sm mt-1">Responda duas perguntas para personalizar sua experiência</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface rounded-xl border border-border p-6 shadow-xl space-y-6">
          {/* Nível */}
          <div>
            <h2 className="font-semibold text-text mb-3">Nível de conhecimento em programação</h2>
            <div className="space-y-2">
              {LEVELS.map(l => (
                <label key={l.id} onClick={() => setLevel(l.id)}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all
                    ${level === l.id
                      ? "border-accent bg-accent/10"
                      : "border-border hover:border-soft hover:bg-panel"}`}>
                  <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 transition-all
                    ${level === l.id ? "border-accent bg-accent" : "border-muted"}`} />
                  <div>
                    <span className="font-medium text-text">{l.label}</span>
                    <span className="text-muted text-sm ml-2">— {l.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Propósito */}
          <div>
            <h2 className="font-semibold text-text mb-1">Propósito de Uso do TutorAndCoder</h2>
            <p className="text-muted text-xs mb-3">Mais de uma opção selecionável</p>
            <div className="space-y-2">
              {PURPOSES.map(p => (
                <label key={p.id} onClick={() => togglePurpose(p.id)}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all
                    ${purposes.includes(p.id)
                      ? "border-accent bg-accent/10"
                      : "border-border hover:border-soft hover:bg-panel"}`}>
                  <div className={`w-4 h-4 rounded border-2 flex-shrink-0 transition-all flex items-center justify-center
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

          <button type="submit" disabled={loading}
            className="w-full bg-accent hover:bg-accent-hover text-white font-semibold py-3
              rounded-lg transition-colors disabled:opacity-50 text-base">
            {loading ? "Salvando..." : "Começar a usar o TutorAndCoder →"}
          </button>
        </form>
      </div>
    </div>
  );
}
