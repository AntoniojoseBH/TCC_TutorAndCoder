import React, { useState } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

interface Props {
  token: string;
  onDone: () => void;
}

export default function ResetPasswordPage({ token, onDone }: Props) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [showPass, setShowPass] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 6) { setError("A senha deve ter pelo menos 6 caracteres."); return; }
    if (password !== confirm) { setError("As senhas não coincidem."); return; }
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/auth/reset-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true",
        },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (r.ok) {
        setSuccess(true);
        setTimeout(() => {
          // Remove token da URL e redireciona para login
          window.history.replaceState({}, "", "/");
          onDone();
        }, 2500);
      } else {
        const d = await r.json().catch(() => ({}));
        setError(d.detail || "Token inválido ou expirado. Solicite um novo link.");
      }
    } catch {
      setError("Não foi possível conectar ao servidor.");
    }
    setLoading(false);
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-4xl mb-2">🔐</div>
          <h1 className="text-2xl font-bold text-text">Redefinir Senha</h1>
          <p className="text-muted text-sm mt-1">TutorAndCoder</p>
        </div>

        <div className="bg-surface border border-border rounded-xl p-6 shadow-xl">
          {success ? (
            <div className="text-center py-4">
              <div className="text-4xl mb-3">✅</div>
              <p className="text-green-400 font-medium">Senha redefinida com sucesso!</p>
              <p className="text-muted text-sm mt-2">Redirecionando para o login...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-soft mb-1.5">Nova senha</label>
                <div className="relative">
                  <input
                    type={showPass ? "text" : "password"}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="Mínimo 6 caracteres"
                    autoFocus
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2.5
                      text-text focus:outline-none focus:border-accent transition-colors pr-10"
                    required minLength={6}
                  />
                  <button type="button" onClick={() => setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text">
                    {showPass ? "🙈" : "👁"}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm text-soft mb-1.5">Confirmar nova senha</label>
                <input
                  type={showPass ? "text" : "password"}
                  value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                  placeholder="Digite a senha novamente"
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5
                    text-text focus:outline-none focus:border-accent transition-colors"
                  required
                />
              </div>

              {error && <p className="text-danger text-sm">{error}</p>}

              <button type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-hover text-white font-medium
                  py-2.5 rounded-lg transition-colors disabled:opacity-50">
                {loading ? "Salvando..." : "Redefinir senha"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
