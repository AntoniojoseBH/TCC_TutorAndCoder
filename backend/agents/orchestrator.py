"""
Orquestrador de Agentes — Agno 2.x
Filtra apenas eventos de conteúdo final (TeamRunEvent.run_content),
ignorando logs internos dos agentes (run_intermediate_content).
"""

from agno.team import Team
from agno.models.anthropic import Claude
from agno.run.team import TeamRunEvent
import json, time, logging, os, re
from typing import AsyncGenerator

from backend.config import settings
from backend.agents.infrastructure import create_infrastructure_agent
from backend.agents.student_model import create_student_model_agent
from backend.agents.pedagogical import create_pedagogical_agent
from backend.agents.evaluation import create_evaluation_agent
from backend.agents.file_editor import create_file_editor_agent
from backend.agents.governance import create_governance_agent

logger = logging.getLogger(__name__)

# Apenas estes eventos contêm o texto final da resposta
CONTENT_EVENTS = {
    TeamRunEvent.run_content.value,         # "TeamRunContent"
    TeamRunEvent.run_completed.value,       # "TeamRunCompleted"
}


def get_model(model_id: str = None):
    mid = model_id or settings.LLM_MODEL
    api_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY nao encontrada no .env")
    return Claude(id=mid, api_key=api_key)


# Padroes de narracao interna do Agno que podem aparecer DENTRO do
# conteudo final gerado pelo Team (nao apenas como eventos separados).
# Cada padrao termina em '.' ou ':' e e removido junto com a pontuacao.
_INTERNAL_NARRATION_PATTERNS = [
    r"Vou coordenar[^.:]*[.:]",
    r"Vou delegar[^.:]*[.:]",
    r"Agora vou delegar[^.:]*[.:]",
    r"Agora vou salvar[^.:]*[.:]",
    r"Vou agora salvar[^.:]*[.:]",
    r"Vou salvar[^.:]*[.:]",
    r"Vou analisar[^.:]*[.:]",
    r"Agora vou analisar[^.:]*[.:]",
    r"Vou agora analisar[^.:]*[.:]",
    r"Vou processar[^.:]*[.:]",
    r"Agora vou processar[^.:]*[.:]",
    r"Vou agora processar[^.:]*[.:]",
    r"Vou chamar[^.:]*[.:]",
    r"Agora vou chamar[^.:]*[.:]",
    r"Vou criar[^.:]*explica[çc][ãa]o[^.:]*[.:]",
    r"Vou (?:agora\s+)?(?:gerar|preparar|elaborar|montar)[^.:]*[.:]",
]

_INTERNAL_NARRATION_RE = re.compile(
    "|".join(_INTERNAL_NARRATION_PATTERNS), flags=re.IGNORECASE
)


def clean_response(text: str) -> str:
    """
    Remove narracao interna de coordenacao do Agno que pode vir embutida
    no conteudo final (ex: 'Vou delegar ao FileEditorAgent para criar...').
    Tambem remove separadores '---' isolados deixados apos a limpeza
    e normaliza espacos/quebras de linha excedentes.
    """
    if not text:
        return text

    cleaned = _INTERNAL_NARRATION_RE.sub("", text)

    # Remove qualquer separador '---' isolado deixado apos a limpeza
    # (independente de estar no inicio, meio ou fim do texto).
    # Usa apenas espacos/tabs (nao \s) ao redor para NAO afetar
    # indentacao de blocos de codigo em linhas proximas.
    cleaned = re.sub(r"[ \t]*-{3,}[ \t]*", "\n\n", cleaned)

    # Colapsa apenas linhas em branco excedentes (preserva indentacao)
    cleaned = re.sub(r"^\s*\n+", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


class AgentOrchestrator:

    def __init__(self, student_id: str, session_id: str, student_profile: dict):
        self.student_id = student_id
        self.session_id = session_id

        difficulty = student_profile.get("difficulty_level", 0.3)
        # Usa nível do onboarding se disponível, senão infere pela dificuldade
        onboarding_level   = student_profile.get("onboarding_level", "")
        onboarding_purpose = student_profile.get("onboarding_purpose", "")
        level = onboarding_level if onboarding_level else (
            "iniciante" if difficulty < 0.4 else
            "intermediario" if difficulty < 0.7 else "avancado"
        )
        weak   = [k for k, v in student_profile.get("concept_mastery", {}).items()
                  if not k.startswith("_") and isinstance(v, (int, float)) and v < 0.5]
        strong = [k for k, v in student_profile.get("concept_mastery", {}).items()
                  if not k.startswith("_") and isinstance(v, (int, float)) and v >= 0.8]

        # Adapta linguagem e exemplos ao propósito do usuário
        purpose_list = [p.strip() for p in onboarding_purpose.split(",") if p.strip()]
        purpose_instruction = ""
        if "academico" in purpose_list:
            purpose_instruction += (
                "O estudante usa o tutor para fins acadêmicos (faculdade, TCC, provas). "
                "Priorize explicações teóricas completas, mencione conceitos formais, "
                "use terminologia acadêmica e indique quando um conceito é cobrado em provas. "
            )
        if "profissional" in purpose_list:
            purpose_instruction += (
                "O estudante usa o tutor para fins profissionais. "
                "Priorize exemplos práticos do mercado de trabalho, boas práticas de produção, "
                "padrões de código limpo e casos de uso reais de empresas. "
            )
        if "hobby" in purpose_list:
            purpose_instruction += (
                "O estudante usa o tutor por hobby e interesse pessoal. "
                "Use linguagem leve e descontraída, faça analogias criativas, "
                "proponha projetos divertidos e valorize a curiosidade. "
            )

        # Adapta profundidade ao nível declarado
        level_instruction = {
            "iniciante":     "Explique com linguagem simples, muitas analogias e exemplos básicos. Evite jargão técnico.",
            "intermediario": "Use terminologia técnica moderada. Equilibre teoria e prática.",
            "avancado":      "Pode usar terminologia avançada, discutir trade-offs, complexidade e arquitetura.",
        }.get(level, "Adapte ao nível do estudante.")

        self.team = Team(
            name="TutorIATeam",
            mode="coordinate",
            model=get_model(settings.LLM_MODEL),
            members=[
                create_governance_agent(),
                create_infrastructure_agent(),
                create_student_model_agent(),
                create_pedagogical_agent(),
                create_evaluation_agent(),
                create_file_editor_agent(),
            ],
            # Habilita memória nativa do Agno — mantém histórico entre turnos
            add_history_to_context=True,
            num_history_runs=10,          # quantos turnos anteriores incluir
            store_history_messages=True,  # persiste no banco de sessão do Agno
            session_id=session_id,        # vincula ao ID de sessão do estudante
            instructions=[
                "Voce e um tutor academico especializado na grade curricular de Engenharia de Computacao.",
                "",
                "AREAS DE CONHECIMENTO — responda sobre qualquer uma destas areas:",
                "  [PROGRAMACAO] Python, Java, C, C++, JavaScript, TypeScript, SQL, Assembly",
                "  [ALGORITMOS]  logica de programacao, estruturas de dados, complexidade, pseudocodigo",
                "  [REDES]       modelo OSI, TCP/IP, HTTP, DNS, roteamento, firewall, VPN, seguranca",
                "  [SO]          processos, threads, memoria, escalonamento, deadlock, filesystem",
                "  [IHC]         usabilidade, prototipacao, avaliacao heuristica, UX/UI",
                "  [BD]          modelagem relacional, SQL, normalizacao, NoSQL, transacoes",
                "  [ES]          requisitos, design patterns, arquitetura de software, testes, UML",
                "  [ARQUITETURA] representacao binaria, CPU, memoria, pipeline, cache",
                "  [MATEMATICA]  logica proposicional, grafos, combinatoria, algebra linear",
                "",
                "REGRA DE ROTEAMENTO — ao receber uma mensagem:",
                "  1. Identifique a area: [PROGRAMACAO], [REDES], [SO], [IHC], etc.",
                "  2. Identifique a linguagem (se aplicavel): Java, Python, C, etc.",
                "  3. Responda integralmente na area e linguagem identificadas.",
                "  4. Exemplos de codigo devem estar na linguagem que o estudante pediu.",
                "",
                f"CONTEXTO DO ESTUDANTE: nivel={level}, dificuldade={difficulty:.2f}",
                f"Conceitos fortes: {strong or ['nenhum']}",
                f"Conceitos a reforcar: {weak or ['nenhum']}",
                f"Estilo de aprendizado: {student_profile.get('learning_style', 'visual')}",
                "",
                "FLUXO DE EXECUCAO:",
                "  1. GovernanceAgent: avalie seguranca. Se BLOCKED, pare.",
                "  2. InfrastructureAgent: salve a interacao.",
                "  3. StudentModelAgent: atualize o perfil com area e conceito identificados.",
                "  4. Roteie pelo tipo de mensagem:",
                "     - Contem codigo       → EvaluationAgent + PedagogicalAgent",
                "     - Criacao de arquivos → FileEditorAgent",
                "     - Qualquer duvida     → PedagogicalAgent",
                "  5. InfrastructureAgent: salve a resposta gerada.",
                "",
                "FORMATO DA RESPOSTA FINAL:",
                "  - Markdown com blocos de codigo na linguagem correta",
                "  - Maximo 500 palavras",
                "  - Nao inclua logs internos, status de ferramentas ou metadados",
                "ENCERRAMENTO CONTEXTUAL:",
                "  - Estudante fez pergunta → termine com desafio ou reflexao",
                "  - Estudante disse 'entendi', 'ok', 'obrigado', 'certo' →",
                "    confirme o entendimento e pergunte se tem duvidas ou quer",
                "    explorar outro aspecto. NAO proponha novo desafio nesses casos.",
            ],
        )

    async def process_message(self, message: str) -> dict:
        """Resposta completa — usa stream=False para resposta limpa e sem duplicatas."""
        start = time.time()
        full_input = f"[student_id={self.student_id}] [session_id={self.session_id}]\n\n{message}"
        try:
            response = await self.team.arun(full_input, stream=False)
            raw_content = response.content if response and response.content else "Sem resposta gerada."
            content = clean_response(str(raw_content))
            return {
                "content": content,
                "response_time_ms": int((time.time() - start) * 1000),
                "success": True,
            }
        except Exception as e:
            logger.error(f"Erro process_message student={self.student_id}: {e}", exc_info=True)
            return {
                "content": "Erro interno. Tente novamente.",
                "response_time_ms": int((time.time() - start) * 1000),
                "success": False,
                "error": str(e),
            }

    async def process_message_stream(self, message: str) -> AsyncGenerator[str, None]:
        """
        Coleta toda a resposta do Team e entrega como chunk único limpo.
        O Team no modo coordinate não faz streaming real token a token —
        ele processa agentes internamente e emite a resposta final completa.
        Tentativas de extrair deltas geram texto corrompido.
        """
        full_input = f"[student_id={self.student_id}] [session_id={self.session_id}]\n\n{message}"
        try:
            # stream=False retorna a resposta completa e limpa
            response = await self.team.arun(full_input, stream=False)
            raw_content = response.content if response and response.content else ""
            content = clean_response(str(raw_content))
            if not content:
                yield "*(sem resposta)*"
                return

            # Simula streaming dividindo a resposta em pedaços de ~15 chars
            # para manter o efeito visual de digitação no frontend
            import asyncio
            chunk_size = 15
            for i in range(0, len(content), chunk_size):
                yield content[i:i + chunk_size]
                await asyncio.sleep(0.01)  # 10ms entre chunks

        except Exception as e:
            logger.error(f"Erro stream student={self.student_id}: {e}", exc_info=True)
            yield f"\n\nErro interno: {e}"


async def build_orchestrator(
    student_id: str, session_id: str, db, redis_client
) -> AgentOrchestrator:
    from sqlalchemy import select
    from backend.db.models import StudentModel

    cache_key = f"profile:{student_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        profile = json.loads(cached)
    else:
        result = await db.execute(
            select(StudentModel).where(StudentModel.student_id == student_id)
        )
        model = result.scalar_one_or_none()
        mastery = model.concept_mastery if model else {}
        profile = {
            "concept_mastery":    mastery,
            "difficulty_level":   model.difficulty_level   if model else 0.3,
            "learning_style":     model.learning_style     if model else "visual",
            "total_interactions": model.total_interactions if model else 0,
            # Dados do onboarding — usados para personalizar as instruções
            "onboarding_level":   mastery.get("_level", ""),
            "onboarding_purpose": mastery.get("_purpose", ""),
        }
        await redis_client.setex(cache_key, 600, json.dumps(profile))

    return AgentOrchestrator(student_id, session_id, profile)