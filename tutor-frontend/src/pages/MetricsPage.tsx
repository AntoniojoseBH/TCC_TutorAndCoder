import React, { useState, useEffect } from "react";
import { apiGet } from "../api";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function MetricsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const r = await apiGet("/metrics/dashboard");
    if (r.ok) setData(await r.json());
    setLoading(false);
  }

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-muted">Carregando métricas...</div>
    </div>
  );

  if (!data) return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-muted">Erro ao carregar métricas.</div>
    </div>
  );

  const uso = data.uso_geral || {};
  const tempo = data.tempo_resposta || {};
  const perfil = data.perfil_onboarding || {};
  const gov = data.governanca || {};
  const sat = data.satisfacao || {};

  const dailyData = Object.entries(uso.uso_por_dia||{}).map(([d,v])=>({day:d.slice(5),msgs:v}));
  const rtData = (tempo.historico||[]).map((r:any,i:number)=>({i:i+1, seg: (r.ms/1000).toFixed(1)}));
  const masteryData = Object.entries(perfil.dominio_conceitos||{}).map(([k,v])=>({
    concept: k.replace(/_/g," "), value: Math.round(Number(v)*100),
  }));

  const Stat = ({label,value,sub}:{label:string;value:any;sub?:string}) => (
    <div className="bg-surface border border-border rounded-xl p-4">
      <p className="text-muted text-xs mb-1">{label}</p>
      <p className="text-2xl font-bold text-text">{value}</p>
      {sub && <p className="text-muted text-xs mt-1">{sub}</p>}
    </div>
  );

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text">📊 Métricas de Uso</h1>
        <button onClick={load} className="text-xs text-muted hover:text-text border border-border
          px-3 py-1.5 rounded-lg transition-colors">
          ↻ Atualizar
        </button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Mensagens totais" value={uso.total_mensagens||0}/>
        <Stat label="Sessões" value={uso.total_sessoes||0}/>
        <Stat label="Msgs por sessão" value={uso.msgs_por_sessao||0}/>
        <Stat label="Tempo médio" value={tempo.media_ms ? `${(tempo.media_ms/1000).toFixed(1)}s` : "—"}/>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Daily usage */}
        <div className="bg-surface border border-border rounded-xl p-4">
          <h3 className="text-sm font-semibold text-text mb-3">📅 Uso diário (30 dias)</h3>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={dailyData}>
                <XAxis dataKey="day" tick={{fontSize:10,fill:"#64748b"}} tickLine={false}/>
                <YAxis tick={{fontSize:10,fill:"#64748b"}} tickLine={false} axisLine={false}/>
                <Tooltip contentStyle={{background:"#1a1f2e",border:"1px solid #2d3748",borderRadius:8,color:"#e2e8f0"}}/>
                <Bar dataKey="msgs" fill="#3b82f6" radius={[3,3,0,0]}/>
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-muted text-sm text-center py-8">Sem dados ainda</p>}
        </div>

        {/* Response time */}
        <div className="bg-surface border border-border rounded-xl p-4">
          <h3 className="text-sm font-semibold text-text mb-3">⚡ Tempo de resposta</h3>
          {rtData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={150}>
                <LineChart data={rtData}>
                  <XAxis dataKey="i" tick={{fontSize:10,fill:"#64748b"}} tickLine={false}/>
                  <YAxis tick={{fontSize:10,fill:"#64748b"}} tickLine={false} axisLine={false}/>
                  <Tooltip contentStyle={{background:"#1a1f2e",border:"1px solid #2d3748",borderRadius:8,color:"#e2e8f0"}}/>
                  <Line type="monotone" dataKey="seg" stroke="#10b981" strokeWidth={2} dot={{r:3,fill:"#10b981"}}/>
                </LineChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-2">
                {[["Mín",tempo.minimo_ms],["Méd",tempo.media_ms],["Máx",tempo.maximo_ms]].map(([l,v])=>(
                  <div key={l as string}><p className="text-xs text-muted">{l}</p>
                  <p className="text-sm font-semibold text-text">{v ? `${(Number(v)/1000).toFixed(1)}s` : "—"}</p></div>
                ))}
              </div>
            </>
          ) : <p className="text-muted text-sm text-center py-8">Sem dados ainda</p>}
        </div>
      </div>

      {/* Profile + Mastery */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Profile */}
        <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
          <h3 className="text-sm font-semibold text-text">👤 Perfil do Estudante</h3>
          {perfil.nivel && <div><span className="text-xs text-muted">Nível: </span>
            <span className="text-sm text-soft font-medium">{perfil.nivel}</span></div>}
          {perfil.proposito && <div><span className="text-xs text-muted">Propósito: </span>
            <span className="text-sm text-soft">{perfil.proposito}</span></div>}
          <div><span className="text-xs text-muted">Conceitos estudados: </span>
            <span className="text-sm text-soft">{perfil.conceitos_estudados||0}</span></div>
          <hr className="border-border"/>
          <h4 className="text-xs font-semibold text-muted uppercase tracking-wider">Governança</h4>
          <div className="grid grid-cols-2 gap-2">
            <div><p className="text-xs text-muted">Avaliações</p>
              <p className="text-lg font-bold text-text">{gov.total_avaliacoes||0}</p></div>
            <div><p className="text-xs text-muted">Bloqueadas</p>
              <p className="text-lg font-bold text-danger">{gov.mensagens_bloqueadas||0}
                <span className="text-xs text-muted ml-1">({gov.taxa_bloqueio_pct||0}%)</span></p></div>
          </div>
        </div>

        {/* Concept mastery */}
        <div className="bg-surface border border-border rounded-xl p-4">
          <h3 className="text-sm font-semibold text-text mb-3">🧠 Domínio por Conceito</h3>
          {masteryData.length > 0 ? (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {masteryData.sort((a,b)=>b.value-a.value).map(d=>(
                <div key={d.concept}>
                  <div className="flex justify-between text-xs mb-0.5">
                    <span className="text-muted capitalize">{d.concept}</span>
                    <span className={d.value>=80?"text-green-400":d.value>=50?"text-yellow-400":"text-red-400"}>
                      {d.value}%
                    </span>
                  </div>
                  <div className="h-1.5 bg-panel rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all
                      ${d.value>=80?"bg-green-400":d.value>=50?"bg-yellow-400":"bg-red-400"}`}
                      style={{width:`${d.value}%`}}/>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-muted text-sm text-center py-8">Interaja no chat para ver o domínio de conceitos</p>}
        </div>
      </div>

      {/* Satisfaction */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-text mb-3">⭐ Satisfação</h3>
        <div className="flex items-center gap-8">
          <div>
            <p className="text-xs text-muted">Total de avaliações</p>
            <p className="text-2xl font-bold text-text">{sat.total_avaliacoes||0}</p>
          </div>
          <div>
            <p className="text-xs text-muted">Média</p>
            <p className="text-2xl font-bold text-text">{sat.media_estrelas ? sat.media_estrelas.toFixed(1) : "—"}</p>
          </div>
          {sat.media_estrelas && (
            <div className="text-2xl">
              {"⭐".repeat(Math.round(sat.media_estrelas))}
            </div>
          )}
        </div>
        {sat.historico?.length > 0 && (
          <div className="mt-3 space-y-1">
            <p className="text-xs text-muted font-medium">Últimas avaliações:</p>
            {sat.historico.slice(-5).reverse().map((f:any,i:number)=>(
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="text-muted">{f.timestamp?.slice(0,16)}</span>
                <span>{"⭐".repeat(f.rating)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
