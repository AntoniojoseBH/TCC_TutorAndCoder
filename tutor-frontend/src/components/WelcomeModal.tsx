import React from "react";
import { MessageSquare, FolderOpen, X } from "lucide-react";

interface Props {
  userName: string;
  onClose: () => void;
}

export default function WelcomeModal({ userName, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-surface border border-border rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-text text-lg">
            Bem-vindo(a), {userName}! 👋
          </h2>
          <button onClick={onClose} className="text-muted hover:text-text transition-colors">
            <X size={18}/>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          <p className="text-soft text-sm">
            Antes de começar, aqui está um resumo rápido de para que serve cada parte do TutorAndCoder:
          </p>

          {/* Conversas */}
          <div className="flex items-start gap-3 p-3 rounded-lg bg-panel border border-border">
            <div className="w-9 h-9 rounded-lg bg-accent/15 flex items-center justify-center flex-shrink-0">
              <MessageSquare size={18} className="text-accent"/>
            </div>
            <div>
              <p className="font-medium text-text text-sm">Conversas</p>
              <p className="text-muted text-xs mt-0.5">
                Tire dúvidas conceituais com o tutor, peça explicações e resolva desafios
                de programação em formato de chat.
              </p>
            </div>
          </div>

          {/* Projetos */}
          <div className="flex items-start gap-3 p-3 rounded-lg bg-panel border border-border">
            <div className="w-9 h-9 rounded-lg bg-accent/15 flex items-center justify-center flex-shrink-0">
              <FolderOpen size={18} className="text-accent"/>
            </div>
            <div>
              <p className="font-medium text-text text-sm">Projetos</p>
              <p className="text-muted text-xs mt-0.5">
                Aqui é onde você cria, edita e analisa <strong>projetos de código completos</strong> —
                inclusive com o auxílio da IA gerando os arquivos para você.
              </p>
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="px-6 pb-6">
          <button onClick={onClose}
            className="w-full bg-accent hover:bg-accent-hover text-white font-medium py-2.5
              rounded-lg transition-colors">
            Entendi, vamos começar!
          </button>
        </div>
      </div>
    </div>
  );
}
