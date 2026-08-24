"""
Helper centralizado para criação do modelo LLM.
Passa a api_key explicitamente, sem depender de variável de ambiente do sistema.
"""
import os
from agno.models.anthropic import Claude
from backend.config import settings


def get_model(model_id: str = None) -> Claude:
    """Retorna instância do Claude com api_key explícita."""
    mid = model_id or settings.LLM_MODEL
    api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY nao encontrada. "
            "Verifique o arquivo .env na raiz do projeto."
        )
    return Claude(id=mid, api_key=api_key)
