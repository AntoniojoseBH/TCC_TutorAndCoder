from pydantic import BaseModel
import bcrypt
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from jose import JWTError, jwt
from datetime import datetime, timedelta
import uuid

from backend.db.connection import get_db
from backend.db.models import Student, StudentModel
from backend.api.schemas import StudentCreate, TokenResponse
from backend.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_student(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Student:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        student_id: str = payload.get("sub")
        if not student_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if not student or not student.is_active:
        raise credentials_exception
    return student


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: StudentCreate, db: AsyncSession = Depends(get_db)):
    # Normaliza e-mail para lowercase antes de verificar duplicata
    email_lower = data.email.strip().lower()
    existing = await db.execute(
        select(Student).where(func.lower(Student.email) == email_lower)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    student = Student(
        email=email_lower,  # sempre salva em lowercase
        name=data.name,
        hashed_password=hash_password(data.password),
    )
    db.add(student)
    await db.flush()

    model = StudentModel(student_id=student.id)
    db.add(model)
    await db.commit()

    token = create_access_token({"sub": student.id})
    return TokenResponse(access_token=token, student_id=student.id, student_name=student.name)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # Busca ignorando maiúsculas/minúsculas
    result = await db.execute(
        select(Student).where(func.lower(Student.email) == form.username.strip().lower())
    )
    student = result.scalar_one_or_none()
    if not student or not verify_password(form.password, student.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    token = create_access_token({"sub": student.id})
    return TokenResponse(access_token=token, student_id=student.id, student_name=student.name)


# ── Recuperação de senha ─────────────────────────────────────────────────────

_recovery_tokens: dict = {}


class RecoverRequest(BaseModel):
    email: str


class ResetRequest(BaseModel):
    token: str
    new_password: str


def _send_recovery_email(to_email: str, name: str, reset_link: str):
    """
    Envia e-mail de recuperação via Gmail com Senha de App.

    Configure no .env:
        SMTP_EMAIL=seu@gmail.com
        SMTP_PASSWORD=senha_de_app_16_digitos

    Para criar Senha de App no Gmail:
        1. Acesse myaccount.google.com/security
        2. Ative Verificação em duas etapas
        3. Pesquise "Senhas de app" e crie uma para "TutorAndCoder"
        4. Cole os 16 dígitos em SMTP_PASSWORD (sem espaços)
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email import charset as email_charset
    from backend.config import Settings

    fresh         = Settings()
    smtp_email    = fresh.SMTP_EMAIL
    smtp_password = fresh.SMTP_PASSWORD

    print(f"[RECOVERY] SMTP_EMAIL: {smtp_email or 'NAO configurado'}", flush=True)

    if not smtp_email or not smtp_password:
        print(f"[RECOVERY] Configure SMTP_EMAIL e SMTP_PASSWORD no .env", flush=True)
        print(f"[RECOVERY] Link manual: {reset_link}", flush=True)
        return

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;
                background:#f9f9f9;padding:32px;border-radius:12px">
      <div style="text-align:center;margin-bottom:24px">
        <span style="font-size:2rem">&#129302;</span>
        <h1 style="color:#2E5FAC;margin:8px 0 0">TutorAndCoder</h1>
      </div>
      <p style="color:#333">Ola, <b>{name}</b>!</p>
      <p style="color:#555">
        Recebemos uma solicitacao para redefinir a senha da sua conta.
        Clique no botao abaixo. O link e valido por <b>1 hora</b>.
      </p>
      <div style="text-align:center;margin:32px 0">
        <a href="{reset_link}"
           style="background:#2E5FAC;color:#fff;padding:14px 32px;
                  border-radius:8px;text-decoration:none;font-weight:bold">
          Redefinir senha
        </a>
      </div>
      <p style="color:#999;font-size:0.8rem;text-align:center">
        Se nao solicitou, ignore este e-mail.
      </p>
    </div>
    """

    try:
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = "TutorAndCoder - Recuperacao de senha"
        msg["From"]    = f"TutorAndCoder <{smtp_email}>"
        msg["To"]      = to_email
        msg.set_content("Abra este e-mail em um cliente compativel com HTML para ver a mensagem completa.")
        msg.add_alternative(html, subtype="html")
        with smtplib.SMTP("smtp.gmail.com", 587, local_hostname="localhost") as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        print(f"[RECOVERY] E-mail enviado para {to_email}", flush=True)

    except smtplib.SMTPAuthenticationError:
        print(f"[RECOVERY ERROR] Autenticacao falhou. Use Senha de App, nao sua senha normal.", flush=True)
        print(f"[RECOVERY] Link manual: {reset_link}", flush=True)
    except Exception as e:
        print(f"[RECOVERY ERROR] {e}", flush=True)
        print(f"[RECOVERY] Link manual: {reset_link}", flush=True)


@router.post("/recover-password")
async def recover_password(
    data: RecoverRequest,
    db: AsyncSession = Depends(get_db),
):
    email_lower = data.email.strip().lower()
    print(f"[RECOVERY] Buscando: {email_lower}", flush=True)

    result = await db.execute(
        select(Student).where(func.lower(Student.email) == email_lower)
    )
    student = result.scalar_one_or_none()
    print(f"[RECOVERY] Estudante encontrado: {'SIM' if student else 'NAO'}", flush=True)

    if student:
        token = secrets.token_urlsafe(32)
        _recovery_tokens[token] = {
            "student_id": student.id,
            "expires": datetime.utcnow() + timedelta(hours=1),
        }
        reset_link = f"http://localhost:3000/?reset_token={token}"
        _send_recovery_email(email_lower, student.name, reset_link)

    return {"ok": True, "message": "Se o e-mail estiver cadastrado, você receberá as instruções."}


@router.post("/reset-password")
async def reset_password(
    data: ResetRequest,
    db: AsyncSession = Depends(get_db),
):
    entry = _recovery_tokens.get(data.token)
    if not entry or entry["expires"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token inválido ou expirado.")

    result = await db.execute(
        select(Student).where(Student.id == entry["student_id"])
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 6 caracteres.")

    student.hashed_password = bcrypt.hashpw(
        data.new_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    await db.commit()

    del _recovery_tokens[data.token]
    return {"ok": True, "message": "Senha redefinida com sucesso."}