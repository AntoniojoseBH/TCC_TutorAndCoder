from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from typing import Optional, Union


# ── Auth ────────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Senha deve ter pelo menos 6 caracteres")
        return v


class StudentLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student_id: str
    student_name: str


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Mensagem não pode ser vazia")
        if len(v) > 10000:
            raise ValueError("Mensagem muito longa (máximo 10000 caracteres)")
        return v.strip()


class ChatResponse(BaseModel):
    content: str
    session_id: str
    response_time_ms: int


# ── Student ─────────────────────────────────────────────────────────────────

class StudentProfile(BaseModel):
    id: str
    name: str
    email: str
    # concept_mastery pode ter floats (conceitos) e strings (metadados _level, _purpose)
    concept_mastery: dict[str, Union[float, str, bool]]
    difficulty_level: float
    learning_style: str
    total_interactions: int
    total_exercises_done: int
    total_correct_exercises: int
    created_at: datetime


class UpdateLearningStyle(BaseModel):
    learning_style: str

    @field_validator("learning_style")
    @classmethod
    def valid_style(cls, v: str) -> str:
        valid = {"visual", "textual", "hands-on"}
        if v not in valid:
            raise ValueError(f"Estilo deve ser um de: {valid}")
        return v


# ── Files ────────────────────────────────────────────────────────────────────

class FileReadRequest(BaseModel):
    path: str


class FileWriteRequest(BaseModel):
    path: str
    content: str


class FilePatchRequest(BaseModel):
    path: str
    old_code: str
    new_code: str


class MultiFileWriteRequest(BaseModel):
    files: dict[str, str]  # {caminho: conteúdo}


class FileOperationResponse(BaseModel):
    success: bool
    path: str
    message: str
    diff: Optional[str] = None