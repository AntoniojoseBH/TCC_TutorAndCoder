from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging, os

from backend.db.connection import create_tables, check_db_connection, check_redis_connection
from backend.api.routes import auth, chat, student, files, projects, analysis, metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando TutorAndCoder API...")
    db_ok    = await check_db_connection()
    redis_ok = await check_redis_connection()
    if not db_ok:    logger.error("⚠️  Banco de dados inacessível!")
    if not redis_ok: logger.warning("⚠️  Redis inacessível.")
    if db_ok: await create_tables()
    logger.info("✅ API pronta.")
    yield
    logger.info("Encerrando API...")

app = FastAPI(
    title="TutorAndCoder — API",
    description="Sistema de IA Agêntica para Apoio ao Aprendizado de Programação",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    #allow_origins=[
     #   "http://localhost:3000",   # React dev server
     #   "http://localhost:8501",   # Streamlit (compatibilidade)
     #   "http://127.0.0.1:3000",
    #],
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,     prefix="/auth",     tags=["autenticação"])
app.include_router(chat.router,     prefix="/chat",     tags=["chat"])
app.include_router(student.router,  prefix="/student",  tags=["estudante"])
app.include_router(files.router,    prefix="/files",    tags=["arquivos"])
app.include_router(projects.router, prefix="/projects", tags=["projetos"])
app.include_router(analysis.router, prefix="/analysis", tags=["analise"])
app.include_router(metrics.router,  prefix="/metrics",  tags=["metricas"])

@app.get("/health")
async def health_check():
    return {"status": "ok",
            "db":    await check_db_connection(),
            "redis": await check_redis_connection()}