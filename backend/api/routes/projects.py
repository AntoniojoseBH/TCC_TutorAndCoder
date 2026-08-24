"""
Endpoint dedicado para geração de projetos completos.
Bypassa o orquestrador multi-agente e chama o FileEditorAgent diretamente,
evitando timeout em operações de criação de múltiplos arquivos.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json
import os
import re

from backend.db.connection import get_db
from backend.db.models import Student
from backend.api.routes.auth import get_current_student
from backend.config import settings
from backend.tools.file_editor import write_multiple_files

router = APIRouter()


def get_model():
    from agno.models.anthropic import Claude
    api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    return Claude(id=settings.LLM_MODEL, api_key=api_key)


def slugify_folder_name(description: str) -> str:
    """
    Gera um nome de pasta curto e válido a partir da descrição do projeto,
    usado como fallback caso a IA não prefixe os arquivos com uma pasta.
    Ex: "Projeto Python de calculadora com main.py..." -> "calculadora"
    """
    text = description.lower()
    # Remove palavras genéricas comuns no início da descrição
    text = re.sub(
        r"^(projeto|crie|criar|gere|gerar|um|uma|de|python|javascript|java)\s+",
        "", text
    )
    # Pega as primeiras palavras significativas
    words = re.findall(r"[a-zà-ú0-9]+", text)[:3]
    slug = "_".join(words) if words else "projeto_gerado"
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug or "projeto_gerado"


def ensure_folder_prefix(files: dict, description: str) -> dict:
    """
    Garante que TODOS os arquivos fiquem dentro de uma pasta de projeto,
    independentemente de a IA ter seguido a instrução ou não.
    Se algum arquivo já tiver "/", usa a primeira pasta encontrada como
    referência para os demais que não tiverem.
    """
    if not files:
        return files

    # Detecta se já existe alguma pasta sendo usada
    existing_folder = None
    for path in files.keys():
        if "/" in path:
            existing_folder = path.split("/")[0]
            break

    folder = existing_folder or slugify_folder_name(description)

    fixed = {}
    for path, content in files.items():
        if "/" in path:
            fixed[path] = content
        else:
            fixed[f"{folder}/{path}"] = content
    return fixed


from pydantic import BaseModel

class ProjectRequest(BaseModel):
    description: str


@router.post("/generate")
async def generate_project(
    request: ProjectRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Gera um projeto completo com múltiplos arquivos diretamente via LLM.
    Retorna streaming SSE com progresso de cada arquivo criado.
    """
    description = request.description
    if not description:
        return {"error": "Descrição do projeto não informada"}

    student_id = current_student.id

    async def generate(sid=student_id):
        student_id = sid
        yield f"data: {json.dumps({'type': 'status', 'message': 'Planejando estrutura do projeto...'})}\n\n"

        # Monta o prompt direto para o LLM gerar os arquivos
        prompt = f"""Você é um assistente que gera projetos de código completos.

Gere um projeto com base nesta descrição:
{description}

Responda APENAS com um objeto JSON válido no seguinte formato, sem texto antes ou depois:
{{
  "project_name": "nome_curto_da_pasta_do_projeto",
  "files": {{
    "nome_do_arquivo.ext": "conteúdo completo do arquivo",
    "outro_arquivo.ext": "conteúdo completo do arquivo"
  }},
  "summary": "resumo do que foi criado em 2-3 frases"
}}

Regras OBRIGATÓRIAS:
- "project_name" deve ser um nome curto, em snake_case, sem espaços e sem acentos
  (ex: "calculadora", "todo_list", "api_flask"), representando a pasta do projeto.
- TODOS os caminhos dentro de "files" DEVEM começar com "project_name/",
  exemplo: se project_name for "calculadora", os arquivos devem ser
  "calculadora/main.py", "calculadora/calculadora.py", "calculadora/README.md".
- NUNCA use caminhos soltos como "main.py" sem o prefixo da pasta do projeto.
  Isso é uma regra crítica: arquivos sem prefixo de pasta aparecem soltos
  fora de qualquer projeto na interface, o que é um erro grave.
- Inclua código funcional e completo em cada arquivo.
- Para README.md, use markdown com descrição, instalação e uso.
- Para arquivos Python, inclua docstrings e comentários.
- Máximo de 8 arquivos por projeto.
"""

        try:
            from agno.agent import Agent
            agent = Agent(
                name="ProjectGenerator",
                model=get_model(),
                instructions=[
                    "Gere projetos de código completos e funcionais.",
                    "Responda SEMPRE com JSON puro, sem markdown, sem explicações fora do JSON.",
                    "O JSON deve ter exatamente as chaves 'project_name', 'files' e 'summary'.",
                    "TODOS os caminhos em 'files' DEVEM começar com 'project_name/' — "
                    "isso é obrigatório e crítico, nunca gere caminhos soltos.",
                ],
            )

            yield f"data: {json.dumps({'type': 'status', 'message': 'Gerando arquivos com IA...'})}\n\n"

            response = await agent.arun(prompt, stream=False)
            raw = response.content if response and response.content else ""

            # Remove possíveis blocos de markdown ao redor do JSON
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0]
            raw = raw.strip()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Tenta extrair JSON do meio do texto
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Erro ao interpretar resposta da IA. Tente uma descrição mais simples.'})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            files = data.get("files", {})
            summary = data.get("summary", "Projeto gerado com sucesso.")

            if not files:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Nenhum arquivo foi gerado. Tente reformular a descrição.'})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Proteção extra: garante prefixo de pasta em TODOS os arquivos,
            # mesmo que a IA não tenha seguido a instrução corretamente.
            files = ensure_folder_prefix(files, description)

            # Salva cada arquivo e reporta progresso
            yield f"data: {json.dumps({'type': 'status', 'message': f'Salvando {len(files)} arquivo(s)...'})}\n\n"

            results = write_multiple_files(student_id, files)

            created = []
            errors = []
            for r in results:
                if r.success:
                    created.append(r.path)
                    yield f"data: {json.dumps({'type': 'file_created', 'path': r.path})}\n\n"
                else:
                    errors.append(f"{r.path}: {r.message}")

            # Monta resposta final formatada
            file_list = "\n".join(f"  - `{f}`" for f in created)
            error_list = ("\n\n⚠️ Erros:\n" + "\n".join(errors)) if errors else ""

            final_message = (
                f"✅ **Projeto criado com sucesso!**\n\n"
                f"{summary}\n\n"
                f"**Arquivos criados ({len(created)}):**\n{file_list}"
                f"{error_list}\n\n"
                f"Você pode ver e editar os arquivos na aba **📁 Projetos**.\n\n"
                f"Quer que eu explique alguma parte do código ou adicione mais funcionalidades?"
            )

            yield f"data: {json.dumps({'type': 'done', 'message': final_message, 'files': created})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Erro ao gerar projeto: {str(e)}'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )