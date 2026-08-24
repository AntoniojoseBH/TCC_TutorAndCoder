import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { apiPost } from "../api";
import logo from "../assets/logo.png";


export default function LoginPage() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState<"login"|"register"|"recover">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault(); setError(""); setLoading(true);
    const err = await login(email, password);
    if (err) setError(err);
    setLoading(false);
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault(); setError(""); setLoading(true);
    const err = await register(name, email, password);
    if (err) setError(err);
    setLoading(false);
  }

  async function handleRecover(e: React.FormEvent) {
    e.preventDefault(); setError(""); setLoading(true);
    try {
      await apiPost("/auth/recover-password", { email }, false);
      setSuccess("Se esse e-mail estiver cadastrado, você receberá as instruções em breve.");
    } catch { setError("Erro ao enviar. Tente novamente."); }
    setLoading(false);
  }

  const switchTab = (t: typeof tab) => {
    setTab(t); setError(""); setSuccess("");
    setEmail(""); setPassword(""); setName("");
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <img src={logo} alt="TutorAndCoder" className="w-48 mx-auto mb-2"/>
          <p className="text-muted text-sm mt-1">Seu assistente pessoal de programação</p>
        </div>

        <div className="bg-surface rounded-xl border border-border p-6 shadow-xl">
          {/* Login */}
          {tab === "login" && (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm text-soft mb-1">E-mail</label>
                <input type="email" value={email} onChange={e=>setEmail(e.target.value)}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                    focus:outline-none focus:border-accent transition-colors"
                  placeholder="seu@email.com" required />
              </div>
              <div>
                <label className="block text-sm text-soft mb-1">Senha</label>
                <div className="relative">
                  <input type={showPass?"text":"password"} value={password}
                    onChange={e=>setPassword(e.target.value)}
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                      focus:outline-none focus:border-accent transition-colors pr-10"
                    placeholder="••••••••" required />
                  <button type="button" onClick={()=>setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text">
                    {showPass ? "🙈" : "👁"}
                  </button>
                </div>
              </div>
              {error && <p className="text-danger text-sm">{error}</p>}
              <button type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2.5
                  rounded-lg transition-colors disabled:opacity-50">
                {loading ? "Entrando..." : "Entrar"}
              </button>
              <button type="button" onClick={() => switchTab("register")}
                className="w-full text-accent font-medium py-2.5 rounded-lg
                  bg-bg hover:bg-accent/15 transition-colors">
                Criar Conta
              </button>
              <div className="text-center">
                <button type="button" onClick={() => switchTab("recover")}
                  className="text-muted text-xs hover:text-soft underline transition-colors">
                  Esqueceu sua senha? Clique aqui
                </button>
              </div>
            </form>
          )}

          {/* Register */}
          {tab === "register" && (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-sm text-soft mb-1">Nome completo</label>
                <input type="text" value={name} onChange={e=>setName(e.target.value)}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                    focus:outline-none focus:border-accent transition-colors"
                  placeholder="Seu nome" required />
              </div>
              <div>
                <label className="block text-sm text-soft mb-1">E-mail</label>
                <input type="email" value={email} onChange={e=>setEmail(e.target.value)}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                    focus:outline-none focus:border-accent transition-colors"
                  placeholder="seu@email.com" required />
              </div>
              <div>
                <label className="block text-sm text-soft mb-1">Senha</label>
                <div className="relative">
                  <input type={showPass?"text":"password"} value={password}
                    onChange={e=>setPassword(e.target.value)}
                    className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                      focus:outline-none focus:border-accent transition-colors pr-10"
                    placeholder="Mínimo 6 caracteres" required minLength={6} />
                  <button type="button" onClick={()=>setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text">
                    {showPass ? "🙈" : "👁"}
                  </button>
                </div>
              </div>
              {error && <p className="text-danger text-sm">{error}</p>}
              <button type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2.5
                  rounded-lg transition-colors disabled:opacity-50">
                {loading ? "Criando conta..." : "Criar conta"}
              </button>
              <button type="button" onClick={() => switchTab("login")}
                className="w-full text-accent font-medium py-2.5 rounded-lg
                  bg-bg hover:bg-accent/15 transition-colors">
                Já tenho uma conta
              </button>
            </form>
          )}

          {/* Recover */}
          {tab === "recover" && (
            <form onSubmit={handleRecover} className="space-y-4">
              <div className="text-center mb-2">
                <p className="text-soft text-sm">Informe seu e-mail cadastrado para receber as instruções de recuperação.</p>
              </div>
              <div>
                <label className="block text-sm text-soft mb-1">E-mail</label>
                <input type="email" value={email} onChange={e=>setEmail(e.target.value)}
                  className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-text
                    focus:outline-none focus:border-accent transition-colors"
                  placeholder="seu@email.com" required />
              </div>
              {error && <p className="text-danger text-sm">{error}</p>}
              {success && <p className="text-green-400 text-sm">{success}</p>}
              <button type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2.5
                  rounded-lg transition-colors disabled:opacity-50">
                {loading ? "Enviando..." : "Enviar"}
              </button>
              <div className="text-center">
                <button type="button" onClick={() => switchTab("login")}
                  className="text-muted text-xs hover:text-soft underline">
                  Voltar para o login
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
