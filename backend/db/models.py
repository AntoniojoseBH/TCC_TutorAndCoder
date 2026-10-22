from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Float, DateTime, ForeignKey, JSON, Text, Integer, Boolean
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    model: Mapped["StudentModel"] = relationship(back_populates="student", uselist=False, cascade="all, delete-orphan")
    exercises: Mapped[list["ExerciseAttempt"]] = relationship(back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student id={self.id} email={self.email}>"


class StudentModel(Base):
    """Modelo cognitivo do estudante — atualizado a cada interação."""
    __tablename__ = "student_models"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), unique=True, nullable=False)

    # Mapa de domínio por conceito: {"loops": 0.8, "recursion": 0.3, ...}
    concept_mastery: Mapped[dict] = mapped_column(JSON, default=dict)

    # Preferências e perfil de aprendizado
    learning_style: Mapped[str] = mapped_column(String, default="visual")  # visual, textual, hands-on
    difficulty_level: Mapped[float] = mapped_column(Float, default=0.3)    # 0.0 = iniciante, 1.0 = avançado
    preferred_language: Mapped[str] = mapped_column(String, default="python")
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    total_exercises_done: Mapped[int] = mapped_column(Integer, default=0)
    total_correct_exercises: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="model")


class Interaction(Base):
    """Histórico completo de todas as mensagens trocadas."""
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)       # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String, nullable=True)      # "question" | "code_submission" | "exercise_request"
    concepts_mentioned: Mapped[list] = mapped_column(JSON, default=list)

    # Embedding vetorial para busca semântica (1536 dims = OpenAI text-embedding-3-small)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=True)

    # Metadados do agente que gerou a resposta
    agent_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    was_flagged: Mapped[bool] = mapped_column(Boolean, default=False)

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    student: Mapped["Student"] = relationship(back_populates="interactions")


class Exercise(Base):
    """Banco de exercícios catalogados por conceito e dificuldade."""
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    concept: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 a 1.0
    expected_solution: Mapped[str] = mapped_column(Text, nullable=True)
    test_cases: Mapped[list] = mapped_column(JSON, default=list)
    hints: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attempts: Mapped[list["ExerciseAttempt"]] = relationship(back_populates="exercise")


class ExerciseAttempt(Base):
    """Registro de cada tentativa de exercício feita pelo estudante."""
    __tablename__ = "exercise_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), nullable=False)
    submitted_code: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    feedback: Mapped[str] = mapped_column(Text, nullable=True)
    execution_output: Mapped[str] = mapped_column(Text, nullable=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=1)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(back_populates="attempts")


class GovernanceLog(Base):
    """Log de auditoria de governança — todas as interações avaliadas."""
    __tablename__ = "governance_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(String, nullable=False)
    message_preview: Mapped[str] = mapped_column(String, nullable=False)  # primeiros 200 chars
    was_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str] = mapped_column(String, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ChatSession(Base):
    """Metadados de sessões de chat — guarda o nome customizado quando
    o estudante renomeia uma conversa. Sem essa tabela, o nome era salvo
    só no Redis, que é volátil e perde o dado a cada reinício."""
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), nullable=False)
    custom_name: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
