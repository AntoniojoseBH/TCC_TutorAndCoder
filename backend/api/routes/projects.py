"""
Endpoint dedicado para geração de projetos completos.

Estratégia em DUAS FASES (plano → execução), para suportar descrições
detalhadas sem estourar o limite de tokens de saída do modelo:

  1. PLANO: uma chamada curta devolve a lista de arquivos do projeto, com o
     propósito e a "interface" (contrato público) de cada um.
  2. EXECUÇÃO: uma chamada por arquivo (em paralelo limitado), cada uma
     devolvendo apenas o código bruto daquele arquivo. Todas recebem o plano
     completo como contexto, o que mantém imports e nomes consistentes entre
     os arquivos.

Antes, o projeto inteiro era pedido em um único JSON com o conteúdo de todos
os arquivos dentro de strings. Com descrições detalhadas, a resposta batia no
limite de tokens e era cortada no meio de uma string, causando o erro
"Unterminated string starting at ...".
"""

import asyncio
import json
import logging
import os
import re

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.connection import get_db
from backend.db.models import Student
from backend.api.routes.auth import get_current_student
from backend.config import settings
from backend.tools.file_editor import write_file

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILES = 25            # teto de arquivos por projeto
MAX_PARALLEL = 4          # chamadas simultâneas à API na fase de execução
PLAN_MAX_TOKENS = 6000    # o plano é curto
FILE_MAX_TOKENS = 16000   # um único arquivo nunca deveria chegar perto disso

# Erros de rede/conexão que valem uma nova tentativa automática
_RETRYABLE_ERROR_KEYWORDS = ("connection", "timeout", "timed out", "network")


# ── Modelo / chamada ao LLM ──────────────────────────────────────────────────

def get_model(max_tokens: int, temperature: float = 0.2):
    from agno.models.anthropic import Claude
    api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    try:
        return Claude(
            id=settings.LLM_MODEL,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except TypeError:
        # Versão do Agno sem suporte a algum desses parâmetros
        logger.warning("Claude() não aceitou max_tokens/temperature — usando padrões.")
        return Claude(id=settings.LLM_MODEL, api_key=api_key)


async def _run_agent(instructions: list, prompt: str, max_tokens: int, retries: int = 3) -> str:
    """
    Executa uma chamada ao LLM com repetição automática em caso de erro de
    conexão ou resposta vazia (backoff exponencial: 1.5s, 3s).
    Erros que não parecem ser de rede são relançados imediatamente.
    """
    from agno.agent import Agent

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            agent = Agent(
                name="ProjectGenerator",
                model=get_model(max_tokens),
                instructions=instructions,
            )
            response = await agent.arun(prompt, stream=False)
            content = str(response.content) if response and response.content else ""
            if content.strip():
                return content
            last_error = RuntimeError("A IA devolveu uma resposta vazia.")
        except Exception as e:  # noqa: BLE001
            last_error = e
            if not any(k in str(e).lower() for k in _RETRYABLE_ERROR_KEYWORDS):
                raise
        if attempt < retries - 1:
            wait = 1.5 * (2 ** attempt)
            logger.warning(
                f"Falha na chamada ao LLM (tentativa {attempt + 1}/{retries}), "
                f"nova tentativa em {wait:.1f}s: {last_error}"
            )
            await asyncio.sleep(wait)

    raise last_error or RuntimeError("Falha desconhecida ao chamar a IA.")


# ── Utilitários ──────────────────────────────────────────────────────────────

def slugify_folder_name(description: str) -> str:
    """
    Gera um nome de pasta curto e válido a partir da descrição do projeto,
    usado como fallback caso a IA não informe um project_name válido.
    """
    text = description.lower()
    text = re.sub(
        r"^(projeto|crie|criar|gere|gerar|um|uma|de|python|javascript|java)\s+",
        "", text,
    )
    words = re.findall(r"[a-zà-ú0-9]+", text)[:3]
    slug = "_".join(words) if words else "projeto_gerado"
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug or "projeto_gerado"


def ensure_folder_prefix(files: dict, description: str) -> dict:
    """
    Garante que TODOS os arquivos fiquem dentro de uma pasta de projeto.
    (Mantida por compatibilidade com outros módulos que possam importá-la.)
    """
    if not files:
        return files
    existing_folder = next((p.split("/")[0] for p in files if "/" in p), None)
    folder = existing_folder or slugify_folder_name(description)
    return {
        (path if "/" in path else f"{folder}/{path}"): content
        for path, content in files.items()
    }


def _strip_code_fences(text: str) -> str:
    """Remove cercas de markdown (```lang ... ```) que o modelo às vezes coloca ao redor."""
    t = text.strip()
    m = re.match(r"^```[A-Za-z0-9_+.\-]*[ \t]*\n(.*)\n```[ \t]*$", t, re.DOTALL)
    if m:
        return m.group(1)
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t


def _extract_json(raw: str) -> dict:
    """Interpreta o JSON do plano, tolerando cercas de markdown e texto ao redor."""
    text = _strip_code_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group())


def _normalize_plan(plan: dict, description: str):
    """
    Valida e normaliza o plano devolvido pela IA:
    - project_name em snake_case sem acentos (com fallback baseado na descrição)
    - caminhos relativos e seguros, todos prefixados com a pasta do projeto
    - sem duplicatas e limitado a MAX_FILES arquivos
    """
    raw_name = str(plan.get("project_name", "")).lower().strip()
    raw_name = re.sub(r"[\s\-]+", "_", raw_name)
    project_name = re.sub(r"[^a-z0-9_]", "", raw_name) or slugify_folder_name(description)

    files, seen = [], set()
    for item in plan.get("files", []) or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip().replace("\\", "/").lstrip("/")
        if not path or ".." in path.split("/"):
            continue
        if not path.startswith(project_name + "/"):
            path = f"{project_name}/{path}"
        if path in seen:
            continue
        seen.add(path)
        files.append({
            "path": path,
            "purpose": str(item.get("purpose", "")).strip(),
            "interface": str(item.get("interface", "")).strip(),
        })

    summary = str(plan.get("summary", "")).strip() or "Projeto gerado com sucesso."
    return project_name, files[:MAX_FILES], summary


def _relative(path: str, project_name: str) -> str:
    prefix = project_name + "/"
    return path[len(prefix):] if path.startswith(prefix) else path


# ── Prompts ──────────────────────────────────────────────────────────────────

PLAN_INSTRUCTIONS = [
    "Você é um arquiteto de software experiente.",
    "Responda SEMPRE com JSON puro e válido, sem markdown e sem texto fora do JSON.",
]

FILE_INSTRUCTIONS = [
    "Você é um desenvolvedor experiente que escreve código completo e funcional.",
    "Responda SEMPRE apenas com o conteúdo bruto do arquivo pedido: sem cercas de "
    "markdown (```), sem explicações antes ou depois, sem placeholders.",
]


def _build_plan_prompt(description: str) -> str:
    return f"""Planeje a estrutura de um projeto de código com base na descrição abaixo.

DESCRIÇÃO DO PROJETO:
{description}

Responda APENAS com um objeto JSON válido neste formato:
{{
  "project_name": "nome_curto_em_snake_case_sem_acentos",
  "summary": "resumo do que será criado, em 2-3 frases",
  "files": [
    {{
      "path": "caminho/relativo/do/arquivo.ext",
      "purpose": "responsabilidade única do arquivo, em 1 frase",
      "interface": "símbolos públicos que o arquivo exporta, com NOMES EXATOS e assinaturas (classes, funções, rotas) e como outros arquivos devem importá-lo"
    }}
  ]
}}

Regras OBRIGATÓRIAS:
- Cubra TODOS os requisitos da descrição, sem omitir nenhum.
- Divida o projeto em arquivos pequenos e coesos (uma responsabilidade por arquivo). \
Prefira vários arquivos curtos a poucos arquivos enormes.
- No máximo {MAX_FILES} arquivos. Inclua README.md e, quando aplicável, arquivo de \
dependências (ex: requirements.txt) e .env.example.
- Os caminhos são RELATIVOS à raiz do projeto: NÃO inclua o nome da pasta do projeto nos caminhos.
- O campo "interface" é o CONTRATO entre os arquivos: nomes de módulos, classes, funções e \
parâmetros devem ser exatamente os que os demais arquivos vão importar e chamar. Seja preciso.
- Se a descrição pedir uma tela/interface, planeje os arquivos dela (HTML/JS/CSS) e como ela consome a API.
"""


def _build_file_prompt(description: str, project_name: str, plan_files: list, target: dict) -> str:
    manifest_lines = []
    for f in plan_files:
        line = f"- {_relative(f['path'], project_name)}: {f['purpose']}"
        if f["interface"]:
            line += f"\n    interface: {f['interface']}"
        manifest_lines.append(line)
    manifest = "\n".join(manifest_lines)

    return f"""Você está gerando UM arquivo de um projeto maior.

DESCRIÇÃO GERAL DO PROJETO:
{description}

ESTRUTURA COMPLETA DO PROJETO (caminhos relativos à raiz do projeto):
{manifest}

ARQUIVO QUE VOCÊ DEVE GERAR AGORA:
- caminho: {_relative(target['path'], project_name)}
- propósito: {target['purpose']}
- interface: {target['interface']}

Regras OBRIGATÓRIAS:
- Responda APENAS com o conteúdo completo do arquivo, sem cercas de markdown (```) e sem explicações.
- Implemente TUDO que a interface acima promete, com código completo e funcional \
(sem "TODO", sem "...", sem placeholders).
- Imports e chamadas para outros arquivos do projeto devem usar EXATAMENTE os nomes de módulos, \
classes e funções definidos na estrutura acima, considerando a raiz do projeto como diretório de execução.
- Em Python, inclua docstrings e comentários breves. Mensagens de erro e textos de interface em português.
- Seja completo, mas objetivo: não repita código que pertence a outros arquivos.
"""


# ── Endpoint ─────────────────────────────────────────────────────────────────

class ProjectRequest(BaseModel):
    description: str


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/generate")
async def generate_project(
    request: ProjectRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Gera um projeto completo em duas fases (plano → um arquivo por chamada).
    Retorna streaming SSE com o progresso de cada etapa e de cada arquivo criado.
    """
    description = (request.description or "").strip()
    if not description:
        return {"error": "Descrição do projeto não informada"}

    student_id = current_student.id

    async def generate(sid=student_id):
        tasks: list[asyncio.Task] = []
        try:
            # ── Fase 1: plano ────────────────────────────────────────────────
            yield _sse({"type": "status", "message": "Planejando estrutura do projeto..."})

            raw_plan = await _run_agent(PLAN_INSTRUCTIONS, _build_plan_prompt(description), PLAN_MAX_TOKENS)
            try:
                plan = _extract_json(raw_plan)
            except json.JSONDecodeError:
                yield _sse({"type": "error", "message": "Não foi possível interpretar o plano do projeto. Tente novamente."})
                yield "data: [DONE]\n\n"
                return

            project_name, plan_files, summary = _normalize_plan(plan, description)
            if not plan_files:
                yield _sse({"type": "error", "message": "A IA não planejou nenhum arquivo. Tente reformular a descrição."})
                yield "data: [DONE]\n\n"
                return

            total = len(plan_files)
            yield _sse({"type": "status", "message": f"Plano definido: {total} arquivo(s). Gerando o código..."})

            # ── Fase 2: um arquivo por chamada, em paralelo limitado ─────────
            semaphore = asyncio.Semaphore(MAX_PARALLEL)

            async def build_one(item: dict):
                async with semaphore:
                    try:
                        prompt = _build_file_prompt(description, project_name, plan_files, item)
                        raw = await _run_agent(FILE_INSTRUCTIONS, prompt, FILE_MAX_TOKENS)
                        content = _strip_code_fences(raw).rstrip() + "\n"
                        result = write_file(sid, item["path"], content)
                        return item["path"], result.success, result.message
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"Falha ao gerar {item['path']}: {e}")
                        return item["path"], False, str(e)

            tasks = [asyncio.create_task(build_one(item)) for item in plan_files]
            order = {item["path"]: i for i, item in enumerate(plan_files)}

            created: list[str] = []
            errors: list[str] = []
            finished_count = 0

            for future in asyncio.as_completed(tasks):
                path, ok, message = await future
                finished_count += 1
                if ok:
                    created.append(path)
                    yield _sse({"type": "file_created", "path": path})
                else:
                    errors.append(f"{path}: {message}")
                yield _sse({"type": "status", "message": f"Arquivos gerados: {finished_count}/{total}"})

            if not created:
                yield _sse({"type": "error", "message": "Nenhum arquivo pôde ser gerado. " + " | ".join(errors[:3])})
                yield "data: [DONE]\n\n"
                return

            # ── Resposta final ───────────────────────────────────────────────
            created.sort(key=lambda p: order.get(p, 0))
            file_list = "\n".join(f"  - `{f}`" for f in created)
            error_list = (
                "\n\n⚠️ Não foi possível gerar alguns arquivos:\n" + "\n".join(f"  - {e}" for e in errors)
                if errors else ""
            )

            final_message = (
                f"✅ **Projeto criado com sucesso!**\n\n"
                f"{summary}\n\n"
                f"**Arquivos criados ({len(created)}):**\n{file_list}"
                f"{error_list}\n\n"
                f"Você pode ver e editar os arquivos na aba **📁 Projetos**.\n\n"
                f"Quer que eu explique alguma parte do código ou adicione mais funcionalidades?"
            )
            yield _sse({"type": "done", "message": final_message, "files": created})

        except Exception as e:  # noqa: BLE001
            logger.error(f"Erro ao gerar projeto: {e}")
            yield _sse({"type": "error", "message": f"Erro ao gerar projeto: {str(e)}"})
        finally:
            # Se o cliente desconectar no meio, cancela as chamadas pendentes
            for t in tasks:
                if not t.done():
                    t.cancel()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )