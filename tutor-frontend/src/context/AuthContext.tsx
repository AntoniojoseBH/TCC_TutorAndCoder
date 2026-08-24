import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getToken, setToken, clearToken, apiGet } from "../api";

interface User { id: string; name: string; onboarding_done: boolean; level?: string; }
interface AuthCtx {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<string | null>;
  register: (name: string, email: string, password: string) => Promise<string | null>;
  logout: () => void;
  setOnboardingDone: (v: boolean) => void;
}

const Ctx = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTok] = useState<string | null>(getToken());

  const loadProfile = useCallback(async () => {
    try {
      const [profileRes, onbRes] = await Promise.all([
        apiGet("/student/profile"),
        apiGet("/student/onboarding-status"),
      ]);
      if (profileRes.ok) {
        const p = await profileRes.json();
        const o = onbRes.ok ? await onbRes.json() : { done: false };
        setUser({ id: p.student_id, name: p.name, onboarding_done: o.done, level: o.level });
      } else {
        logout();
      }
    } catch {
      logout();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (token) loadProfile();
  }, [token, loadProfile]);

  async function login(email: string, password: string): Promise<string | null> {
    try {
      const r = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: email, password }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        return (e.detail as string) || "E-mail ou senha inválidos";
      }
      const d = await r.json();
      setToken(d.access_token);
      setTok(d.access_token);
      setUser({ id: d.student_id, name: d.student_name, onboarding_done: false });
      return null;
    } catch (e) {
      return "Não foi possível conectar ao servidor. Verifique se o backend está rodando.";
    }
  }

  async function register(name: string, email: string, password: string): Promise<string | null> {
    try {
      const r = await fetch("http://localhost:8000/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        const detail = e.detail;
        if (Array.isArray(detail)) {
          const field = detail[0]?.loc?.slice(-1)[0] || "campo";
          const labels: Record<string, string> = { password: "senha", email: "e-mail", name: "nome" };
          return `O campo '${labels[field] || field}' é obrigatório.`;
        }
        return (detail as string) || "Erro ao criar conta";
      }
      const d = await r.json();
      setToken(d.access_token);
      setTok(d.access_token);
      setUser({ id: d.student_id, name: d.student_name, onboarding_done: false });
      return null;
    } catch {
      return "Não foi possível conectar ao servidor. Verifique se o backend está rodando.";
    }
  }

  function logout() { clearToken(); setTok(null); setUser(null); }
  function setOnboardingDone(v: boolean) {
    setUser(u => u ? { ...u, onboarding_done: v } : u);
  }

  return (
    <Ctx.Provider value={{ user, token, login, register, logout, setOnboardingDone }}>
      {children}
    </Ctx.Provider>
  );
}
