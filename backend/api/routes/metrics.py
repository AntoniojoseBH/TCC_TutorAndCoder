"""
Endpoints de métricas do sistema TutorAndCoder.
Registra e consulta: tempo de resposta, satisfação, onboarding, uso geral.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, Integer
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import json

from backend.db.connection import get_db, redis_client
from backend.db.models import Student, StudentModel, Interaction, GovernanceLog
from backend.api.routes.auth import get_current_student

router = APIRouter()


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: Optional[str] = None
    rating: int          # 1 a 5
    comment: Optional[str] = None


class MetricEvent(BaseModel):
    event_type: str      # "response_time" | "onboarding" | "exercise_attempt"
    session_id: str
    value: float
    metadata: Optional[dict] = None


# ── Registro de métricas ─────────────────────────────────────────────────────

@router.post("/event")
async def record_metric_event(
    event: MetricEvent,
    current_student: Student = Depends(get_current_student),
):
    """Registra um evento de métrica no Redis para agregação posterior."""
    key = f"metric:{event.event_type}:{current_student.id}:{datetime.utcnow().timestamp()}"
    data = {
        "student_id": current_student.id,
        "event_type": event.event_type,
        "session_id": event.session_id,
        "value": event.value,
        "metadata": event.metadata or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    await redis_client.setex(key, 60 * 60 * 24 * 30, json.dumps(data))  # 30 dias
    # Adiciona à lista global de métricas do tipo
    await redis_client.lpush(f"metrics_list:{event.event_type}", json.dumps(data))
    await redis_client.ltrim(f"metrics_list:{event.event_type}", 0, 9999)
    return {"ok": True}


@router.post("/feedback")
async def record_feedback(
    feedback: FeedbackRequest,
    current_student: Student = Depends(get_current_student),
):
    """Registra avaliação do estudante sobre uma resposta (1-5 estrelas)."""
    data = {
        "student_id": current_student.id,
        "session_id": feedback.session_id,
        "rating": feedback.rating,
        "comment": feedback.comment or "",
        "timestamp": datetime.utcnow().isoformat(),
    }
    await redis_client.lpush("metrics_list:feedback", json.dumps(data))
    await redis_client.ltrim("metrics_list:feedback", 0, 9999)
    return {"ok": True}


# ── Consulta de métricas ─────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_metrics_dashboard(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna métricas completas do sistema para o dashboard do TCC.
    Inclui: tempo de resposta, satisfação, onboarding, uso geral.
    """
    student_id = current_student.id

    # ── 1. Métricas de uso geral ──────────────────────────────────────────
    total_interactions = await db.execute(
        select(func.count(Interaction.id))
        .where(Interaction.student_id == student_id)
    )
    total_msgs = total_interactions.scalar() or 0

    total_sessions = await db.execute(
        select(func.count(func.distinct(Interaction.session_id)))
        .where(Interaction.student_id == student_id)
    )
    total_sess = total_sessions.scalar() or 0

    # Mensagens por dia (últimos 30 dias)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_result = await db.execute(
        select(
            func.date(Interaction.timestamp).label("day"),
            func.count(Interaction.id).label("count"),
        )
        .where(Interaction.student_id == student_id)
        .where(Interaction.timestamp >= thirty_days_ago)
        .where(Interaction.role == "user")
        .group_by(func.date(Interaction.timestamp))
        .order_by(func.date(Interaction.timestamp))
    )
    daily_usage = {str(r.day): r.count for r in daily_result.all()}

    # ── 2. Tempo de resposta ──────────────────────────────────────────────
    rt_result = await db.execute(
        select(
            func.avg(Interaction.response_time_ms).label("avg_rt"),
            func.min(Interaction.response_time_ms).label("min_rt"),
            func.max(Interaction.response_time_ms).label("max_rt"),
        )
        .where(Interaction.student_id == student_id)
        .where(Interaction.response_time_ms.isnot(None))
    )
    rt_row = rt_result.one()

    # Tempos de resposta detalhados dos últimos 20
    recent_rt = await db.execute(
        select(Interaction.response_time_ms, Interaction.timestamp)
        .where(Interaction.student_id == student_id)
        .where(Interaction.response_time_ms.isnot(None))
        .order_by(Interaction.timestamp.desc())
        .limit(20)
    )
    rt_series = [
        {"time": str(r.timestamp)[:16], "ms": r.response_time_ms}
        for r in recent_rt.all()
    ]

    # ── 3. Perfil do estudante (onboarding) ───────────────────────────────
    model_result = await db.execute(
        select(StudentModel).where(StudentModel.student_id == student_id)
    )
    model = model_result.scalar_one_or_none()

    onboarding_level   = ""
    onboarding_purpose = ""
    concept_mastery    = {}
    if model:
        mastery = model.concept_mastery or {}
        onboarding_level   = mastery.get("_level", "não informado")
        onboarding_purpose = mastery.get("_purpose", "não informado")
        concept_mastery    = {k: v for k, v in mastery.items() if not k.startswith("_")}

    # ── 4. Governança ─────────────────────────────────────────────────────
    gov_result = await db.execute(
        select(
            func.count(GovernanceLog.id).label("total"),
            func.sum(GovernanceLog.was_blocked.cast(Integer)).label("blocked"),
            func.avg(GovernanceLog.risk_score).label("avg_risk"),
        )
        .where(GovernanceLog.student_id == student_id)
    )
    gov_row = gov_result.one()

    # ── 5. Feedback (do Redis) ─────────────────────────────────────────────
    feedback_raw = await redis_client.lrange("metrics_list:feedback", 0, -1)
    feedbacks = []
    for f in feedback_raw:
        try:
            d = json.loads(f)
            if d.get("student_id") == student_id:
                feedbacks.append(d)
        except Exception:
            pass

    avg_rating = (
        sum(f["rating"] for f in feedbacks) / len(feedbacks)
        if feedbacks else None
    )

    return {
        "uso_geral": {
            "total_mensagens":  total_msgs,
            "total_sessoes":    total_sess,
            "msgs_por_sessao":  round(total_msgs / total_sess, 1) if total_sess else 0,
            "uso_por_dia":      daily_usage,
        },
        "tempo_resposta": {
            "media_ms":  round(rt_row.avg_rt or 0),
            "minimo_ms": rt_row.min_rt or 0,
            "maximo_ms": rt_row.max_rt or 0,
            "historico": list(reversed(rt_series)),
        },
        "perfil_onboarding": {
            "nivel":    onboarding_level,
            "proposito": onboarding_purpose,
            "conceitos_estudados": len(concept_mastery),
            "dominio_conceitos": concept_mastery,
        },
        "governanca": {
            "total_avaliacoes":  gov_row.total or 0,
            "mensagens_bloqueadas": int(gov_row.blocked or 0),
            "score_risco_medio": round(float(gov_row.avg_risk or 0), 3),
            "taxa_bloqueio_pct": round(
                int(gov_row.blocked or 0) / (gov_row.total or 1) * 100, 1
            ),
        },
        "satisfacao": {
            "total_avaliacoes": len(feedbacks),
            "media_estrelas":   round(avg_rating, 2) if avg_rating else None,
            "historico":        feedbacks[-10:],
        },
    }