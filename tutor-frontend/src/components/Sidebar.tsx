import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { MessageSquare, FolderOpen, BarChart2, Settings, LogOut, ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  page: string;
  setPage: (p: string) => void;
}

// Oculta "Métricas" da sidebar durante o período de avaliação com usuários
// (a página não é usada pelos participantes — só pelo avaliador). Volte
// para "true" depois de concluída a avaliação para reexibi-la.
const SHOW_METRICS = false;

export default function Sidebar({ page, setPage }: Props) {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  

  const nav = [
    { id: "chat",     icon: <MessageSquare size={18}/>, label: "Conversas" },
    { id: "projects", icon: <FolderOpen size={18}/>,    label: "Projetos" },
    ...(SHOW_METRICS ? [{ id: "metrics", icon: <BarChart2 size={18}/>, label: "Métricas" }] : []),
  ];

  return (
    <aside className={`flex flex-col bg-surface border-r border-border h-screen transition-all duration-200
      ${collapsed ? "w-14" : "w-56"} flex-shrink-0`}>

      {/* Logo */}
      <div className={`flex items-center gap-2 px-3 py-4 border-b border-border`}>
        <span className="text-xl flex-shrink-0">🤖</span>
        {!collapsed && <span className="font-bold text-text text-sm">TutorAndCoder</span>}
        <button onClick={() => setCollapsed(!collapsed)}
          className="ml-auto text-muted hover:text-text transition-colors">
          {collapsed ? <ChevronRight size={16}/> : <ChevronLeft size={16}/>}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 space-y-1 px-2">
        {nav.map(item => (
          <button key={item.id} onClick={() => setPage(item.id)}
            title={collapsed ? item.label : ""}
            className={`w-full flex items-center gap-3 px-2 py-2.5 rounded-lg text-sm
              font-medium transition-all
              ${page === item.id
                ? "bg-white/10 text-white"
                : "text-muted hover:text-text hover:bg-panel"}`}>
            <span className="flex-shrink-0">{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {/* User section */}
      <div className="border-t border-border p-2">
        {/* Level badge */}
        {!collapsed && user?.level && (
          <div className="px-2 py-1.5 mb-2">
            <span className="text-xs text-muted">Nível: </span>
            <span className="text-xs text-soft font-medium">{user.level}</span>
          </div>
        )}

        {/* Configure profile */}
        <button onClick={() => setPage("profile")}
          title={collapsed ? "Configurar perfil" : ""}
          className="w-full flex items-center gap-3 px-2 py-2 rounded-lg text-sm
            text-muted hover:text-text hover:bg-panel transition-all">
          <Settings size={16} className="flex-shrink-0"/>
          {!collapsed && <span>Configurar perfil</span>}
        </button>

        {/* User info + logout */}
        <div className={`flex items-center gap-2 px-2 py-2 mt-1 rounded-lg
          hover:bg-panel transition-all cursor-default`}>
          <div className="w-7 h-7 rounded-full bg-accent/20 flex items-center justify-center
            text-accent text-xs font-bold flex-shrink-0">
            {user?.name?.charAt(0).toUpperCase()}
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text truncate">{user?.name}</p>
            </div>
          )}
          <button onClick={logout} title="Sair"
            className="text-muted hover:text-danger transition-colors flex-shrink-0">
            <LogOut size={14}/>
          </button>
        </div>
      </div>
    </aside>
  );
}
