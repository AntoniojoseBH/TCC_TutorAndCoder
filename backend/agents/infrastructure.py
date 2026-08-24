"""
Agente de Infraestrutura de Dados

Responsabilidades:
- Registrar todas as interações no PostgreSQL
- Gerar embeddings vetoriais para busca semântica
- Recuperar histórico relevante via similarity search
- Manter o contexto de sessão no Redis
"""

from agno.agent import Agent
from agno.models.anthropic import Claude
from backend.agents._model import get_model
from agno.tools import tool
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import json
import time
import logging

from backend.config import settings
from backend.db.models import Interaction, Student
from backend.db.connection import AsyncSessionLocal, redis_client

logger = logging.getLogger(__name__)

SESSION_TTL = 3600  # 1 hora de TTL para sessões no Redis


@tool
async def save_interaction(
    student_id: str,
    session_id: str,
    role: str,
    content: str,
    intent: str = "general",
    concepts_mentioned: list = None,
    agent_metadata: dict = None,
    response_time_ms: int = None,
) -> str:
    """Salva uma interação no banco de dados e atualiza o cache Redis."""
    async with AsyncSessionLocal() as db:
        interaction = Interaction(
            student_id=student_id,
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            concepts_mentioned=concepts_mentioned or [],
            agent_metadata=agent_metadata or {},
            response_time_ms=response_time_ms,
        )
        db.add(interaction)
        await db.commit()

        # Atualiza histórico de sessão no Redis
        session_key = f"session:{session_id}"
        session_data = await redis_client.get(session_key)
        history = json.loads(session_data) if session_data else []
        history.append({"role": role, "content": content[:500]})  # trunca para o cache
        # Mantém apenas as últimas 20 mensagens na sessão
        if len(history) > 20:
            history = history[-20:]
        await redis_client.setex(session_key, SESSION_TTL, json.dumps(history))

    return f"Interação salva. Total na sessão: {len(history)}"


@tool
async def get_session_history(session_id: str, limit: int = 10) -> str:
    """Recupera o histórico recente de uma sessão do Redis."""
    session_key = f"session:{session_id}"
    session_data = await redis_client.get(session_key)
    if not session_data:
        return "[]"
    history = json.loads(session_data)
    return json.dumps(history[-limit:])


@tool
async def search_similar_interactions(student_id: str, query: str, limit: int = 5) -> str:
    """
    Busca interações semanticamente similares no histórico do estudante.
    Útil para identificar dúvidas recorrentes e evitar repetição.
    """
    async with AsyncSessionLocal() as db:
        # Busca as interações mais recentes como fallback (sem embedding por ora)
        result = await db.execute(
            select(Interaction)
            .where(Interaction.student_id == student_id)
            .where(Interaction.role == "user")
            .order_by(desc(Interaction.timestamp))
            .limit(limit * 2)
        )
        interactions = result.scalars().all()

        # Filtragem simples por palavras-chave enquanto embeddings não estão ativos
        query_words = set(query.lower().split())
        scored = []
        for i in interactions:
            content_words = set(i.content.lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                scored.append((overlap, i))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [i.content for _, i in scored[:limit]]

    if not top:
        return "Nenhuma interação similar encontrada."
    return json.dumps(top)


@tool
async def get_interaction_count(student_id: str) -> str:
    """Retorna o total de interações do estudante."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Interaction).where(Interaction.student_id == student_id)
        )
        count = len(result.scalars().all())
    return str(count)


def create_infrastructure_agent() -> Agent:
    return Agent(
        name="InfrastructureAgent",
        role="Agente de Infraestrutura de Dados",
        model=get_model(settings.LLM_MODEL_FAST),
        tools=[save_interaction, get_session_history, search_similar_interactions, get_interaction_count],
        instructions=[
            "Você gerencia o armazenamento e recuperação de dados do sistema.",
            "Salve cada interação do estudante com metadados completos.",
            "Use search_similar_interactions para identificar padrões de dúvidas.",
            "Mantenha o histórico de sessão atualizado no Redis.",
            "Seja preciso e eficiente — não adicione comentários desnecessários.",
        ],
    )
