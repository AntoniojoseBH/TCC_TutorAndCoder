from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.connection import get_db, redis_client
from backend.db.models import Student, StudentModel, Interaction, ExerciseAttempt
from backend.api.schemas import StudentProfile, UpdateLearningStyle
from backend.api.routes.auth import get_current_student

router = APIRouter()


@router.get("/profile", response_model=StudentProfile)
async def get_profile(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Retorna o perfil completo do estudante autenticado."""
    result = await db.execute(
        select(StudentModel).where(StudentModel.student_id == current_student.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")

    return StudentProfile(
        id=current_student.id,
        name=current_student.name,
        email=current_student.email,
        concept_mastery=model.concept_mastery,
        difficulty_level=model.difficulty_level,
        learning_style=model.learning_style,
        total_interactions=model.total_interactions,
        total_exercises_done=model.total_exercises_done,
        total_correct_exercises=model.total_correct_exercises,
        created_at=current_student.created_at,
    )


@router.get("/progress")
async def get_progress(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Retorna dados de progresso para o dashboard do estudante."""
    result = await db.execute(
        select(StudentModel).where(StudentModel.student_id == current_student.id)
    )
    model = result.scalar_one_or_none()

    # Busca últimas 7 interações para o gráfico de atividade
    interactions_result = await db.execute(
        select(Interaction)
        .where(Interaction.student_id == current_student.id)
        .where(Interaction.role == "user")
        .order_by(Interaction.timestamp.desc())
        .limit(50)
    )
    interactions = interactions_result.scalars().all()

    # Agrupa por dia para gráfico de atividade
    from collections import Counter
    activity = Counter(i.timestamp.strftime("%Y-%m-%d") for i in interactions)

    return {
        "concept_mastery": model.concept_mastery if model else {},
        "difficulty_level": model.difficulty_level if model else 0.3,
        "total_interactions": model.total_interactions if model else 0,
        "total_exercises_done": model.total_exercises_done if model else 0,
        "total_correct_exercises": model.total_correct_exercises if model else 0,
        "accuracy_rate": (
            model.total_correct_exercises / model.total_exercises_done
            if model and model.total_exercises_done > 0 else 0.0
        ),
        "activity_by_day": dict(activity),
        "concepts_mastered": sum(
            1 for v in (model.concept_mastery or {}).values() if v >= 0.8
        ),
    }


@router.patch("/learning-style")
async def update_learning_style(
    data: UpdateLearningStyle,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Atualiza o estilo de aprendizado preferido do estudante."""
    result = await db.execute(
        select(StudentModel).where(StudentModel.student_id == current_student.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")

    model.learning_style = data.learning_style
    await db.commit()
    await redis_client.delete(f"profile:{current_student.id}")  # invalida cache

    return {"message": f"Estilo atualizado para '{data.learning_style}'"}


# ── Onboarding ──────────────────────────────────────────────────────────────

LEVEL_TO_DIFFICULTY = {
    "iniciante":     0.2,
    "intermediario": 0.5,
    "avancado":      0.8,
}

PURPOSE_LABELS = {
    "academico":     "Estudos Acadêmicos",
    "profissional":  "Atividades Profissionais",
    "hobby":         "Hobby / Interesse Pessoal",
}

LEVEL_LABELS = {
    "iniciante":     "Iniciante",
    "intermediario": "Intermediário",
    "avancado":      "Avançado",
}


class OnboardingData(BaseModel):
    level: str              # iniciante | intermediario | avancado
    purpose: list[str]      # lista: academico, profissional, hobby


@router.post("/onboarding")
async def save_onboarding(
    data: OnboardingData,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Salva o questionário de onboarding e configura o perfil inicial do estudante."""
    result = await db.execute(
        select(StudentModel).where(StudentModel.student_id == current_student.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")

    # Configura nível de dificuldade baseado na resposta do usuário
    difficulty = LEVEL_TO_DIFFICULTY.get(data.level, 0.3)
    model.difficulty_level = difficulty

    # Salva nível e propósito como metadados no conceito especial "onboarding"
    model.concept_mastery = {
        **model.concept_mastery,
        "_level": data.level,
        "_purpose": ",".join(data.purpose),
        "_onboarding_done": True,
    }

    await db.commit()

    # Invalida cache
    await redis_client.delete(f"profile:{current_student.id}")

    return {
        "ok": True,
        "level": LEVEL_LABELS.get(data.level, data.level),
        "purpose": ", ".join(PURPOSE_LABELS.get(p, p) for p in data.purpose),
        "difficulty_level": difficulty,
    }


@router.get("/onboarding-status")
async def get_onboarding_status(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Verifica se o usuário já completou o onboarding."""
    result = await db.execute(
        select(StudentModel).where(StudentModel.student_id == current_student.id)
    )
    model = result.scalar_one_or_none()
    if not model:
        return {"done": False}

    done = model.concept_mastery.get("_onboarding_done", False)
    level = model.concept_mastery.get("_level", "")
    purpose = model.concept_mastery.get("_purpose", "")

    return {
        "done": done,
        "level": LEVEL_LABELS.get(level, level),
        "purpose": PURPOSE_LABELS.get(purpose, purpose),
        "difficulty_level": model.difficulty_level,
    }

