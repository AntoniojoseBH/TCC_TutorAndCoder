from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from backend.config import settings
from backend.db.models import Base
import logging

logger = logging.getLogger(__name__)

# ── PostgreSQL ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,   # verifica conexões antes de usar
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Redis ───────────────────────────────────────────────────────────────────
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)


async def get_db() -> AsyncSession:
    """Dependency injection do FastAPI para sessão do banco."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables():
    """Cria todas as tabelas e habilita extensão pgvector."""
    logger.info("Criando tabelas no banco de dados...")
    async with engine.begin() as conn:
        # Habilita extensão vetorial do PostgreSQL
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tabelas criadas com sucesso.")


async def check_db_connection() -> bool:
    """Verifica se o banco está acessível."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco: {e}")
        return False


async def check_redis_connection() -> bool:
    """Verifica se o Redis está acessível."""
    try:
        await redis_client.ping()
        return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao Redis: {e}")
        return False
