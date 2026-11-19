"""
Orquestrador de Agentes — Agno 2.x
Filtra apenas eventos de conteúdo final (TeamRunEvent.run_content),
ignorando logs internos dos agentes (run_intermediate_content).
"""

from agno.team import Team
from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.run.team import TeamRunEvent
from agno.media import Image, File
import json, time, logging, os, re, base64, asyncio
from typing import AsyncGenerator, Optional

from backend.config import settings
from backend.agents.infrastructure import create_infrastructure_agent
from backend.agents.student_model import create_student_model_agent
from backend.agents.pedagogical import create_pedagogical_agent
from backend.agents.evaluation import create_evaluation_agent
from backend.agents.file_editor import create_file_editor_agent
from backend.agents.governance import create_governance_agent

logger = logging.getLogger(__name__)

# MARCADOR DE VERSAO — aparece assim que este arquivo e importado pelo
# backend (ou seja, quase imediatamente ao iniciar o uvicorn). Se essa
# linha NAO aparecer no terminal ao subir o backend, o arquivo que esta
# rodando NAO e este — tem outra copia sendo carregada de algum lugar.
logger.warning("### orchestrator.py CARREGADO — versao com retry + fallback Gemini (v5) ###")

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


def _get_fallback_model():
    """
    Modelo de apoio (Google Gemini, plano gratuito) — usado SOMENTE quando
    todas as tentativas com a Claude falharem, para evitar deixar o
    estudante sem nenhuma resposta durante uma instabilidade da Anthropic.
    Retorna None se a chave nao estiver configurada (fallback desativado).
    """
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.warning(
            "Fallback (Gemini) desativado: GEMINI_API_KEY nao encontrada "
            "nem em settings nem nas variaveis de ambiente."
        )
        return None
    return Gemini(id="gemini-2.5-flash", api_key=api_key)


async def _call_fallback_provider(message: str) -> Optional[str]:
    """
    Chama o provedor de apoio (Gemini) diretamente, com um agente simples,
    avisando o estudante que essa e uma resposta de contingencia — sem
    o contexto refinado dos 6 agentes especializados, mas melhor do que
    nenhuma resposta durante uma instabilidade da Anthropic.
    Retorna None se o fallback nao estiver configurado ou tambem falhar.
    """
    fallback_model = _get_fallback_model()
    if fallback_model is None:
        return None
    logger.warning("Tentando provedor de apoio (Gemini) apos falha da Claude...")
    try:
        fallback_agent = Agent(
            name="FallbackAgent",
            model=fallback_model,
            instructions=[
                "Voce e um tutor de Engenharia de Computacao atuando como",
                "resposta de contingencia, pois o servico principal esta",
                "temporariamente indisponivel por instabilidade de conexao.",
                "Responda a duvida do estudante da melhor forma possivel,",
                "de forma clara e direta, em portugues.",
            ],
        )
        response = await fallback_agent.arun(message, stream=False)
        content = response.content if response and response.content else None
        if not content:
            return None
        aviso = (
            "\n\n---\n*⚠️ Esta resposta foi gerada por um servico de apoio, "
            "pois o tutor principal esta temporariamente instavel. "
            "Algumas funcionalidades avancadas podem nao estar disponiveis "
            "nesta resposta.*"
        )
        return str(content) + aviso
    except Exception as e:
        logger.error(f"Fallback (Gemini) tambem falhou: {e}")
        return None


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


# Tipos de mídia tratados como imagem (enviados via parâmetro images=)
_IMAGE_MEDIA_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
# Tipos de mídia tratados como documento binário (enviados via parâmetro files=)
_DOCUMENT_MEDIA_TYPES = {"application/pdf"}


def _prepare_attachment(attachment: Optional[dict]):
    """
    Converte o anexo recebido do frontend (base64 + media_type) no formato
    que o Agno espera.
    Retorna (images, files, extra_text):
      - images: lista de agno.media.Image, se o anexo for uma imagem
      - files:  lista de agno.media.File, se o anexo for um PDF
      - extra_text: texto do arquivo já decodificado, se for texto/código puro
                     (mais confiável do que mandar como File para conteúdo textual)
    """
    if not attachment:
        return [], [], None

    media_type = attachment.get("media_type", "")
    filename = attachment.get("filename", "arquivo")
    b64data = attachment.get("data", "")

    try:
        raw_bytes = base64.b64decode(b64data)
    except Exception:
        logger.warning(f"Falha ao decodificar anexo {filename} (base64 inválido)")
        return [], [], None

    if media_type in _IMAGE_MEDIA_TYPES:
        return [Image(content=raw_bytes)], [], None

    if media_type in _DOCUMENT_MEDIA_TYPES:
        return [], [File(content=raw_bytes)], None

    # Texto/código: decodifica e injeta como texto no prompt — mais confiável
    # para o modelo do que tratar como documento binário
    try:
        text_content = raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        text_content = "(não foi possível ler o conteúdo do arquivo)"

    extra_text = (
        f"\n\n[ARQUIVO ANEXADO: {filename}]\n"
        f"```\n{text_content[:8000]}\n```"
    )
    return [], [], extra_text


# Erros de rede/conexão que valem a pena tentar de novo automaticamente —
# instabilidades intermitentes de rota até a Anthropic, não erros de código
# ou de autenticação (esses não devem ser tentados de novo).
_RETRYABLE_ERROR_KEYWORDS = ("connection", "timeout", "timed out", "network")

# Quando um agente-membro falha por conexão DURANTE a coordenação, o Team às
# vezes não lança exceção nenhuma — o próprio LLM coordenador "decide"
# responder direto e narra essa decisão no texto final (ex: "Deixe-me
# responder diretamente, pois os agentes especializados estão indisponíveis").
# Isso não é pego pelo bloco except acima, pois team.arun() retorna com
# sucesso — precisa ser detectado pelo CONTEÚDO da resposta.
_DEGRADED_FALLBACK_RE = re.compile(
    r"agentes?\s+especializados?\s+(est[ãa]o|est[áa])\s+indispon[íi]ve",
    re.IGNORECASE,
)


async def _arun_with_retry(
    team: Team, full_input: str, images: list, files: list,
    original_message: str = "", max_retries: int = 3, base_delay: float = 1.5,
):
    """
    Chama team.arun() com repetição automática em caso de:
      1) Erro de conexão intermitente com a API da Anthropic que exploda
         como exceção (ex: falha ao chamar o coordenador do Team).
      2) Resposta "degradada" — o Team respondeu com sucesso (sem exceção),
         mas o conteúdo revela que os agentes especializados falharam por
         conexão durante a coordenação e o LLM decidiu responder sozinho.
      3) Resposta VAZIA/None — o Agno às vezes registra internamente o log
         "ERROR Connection error while calling Claude API" / "Error in
         Team run: Connection error." e ENGOLE a exceção por completo,
         sem relançá-la e sem gerar texto de fallback — devolve apenas
         um response vazio ou None. Isso não é pego nem pelo except
         (nenhuma exceção chega até aqui) nem pela checagem de texto
         degradado (não há texto nenhum) — por isso precisa de checagem
         própria.
    Todos os casos são tratados como falha temporária e tentados de novo,
    com backoff exponencial (1.5s, 3s, 6s). Na última tentativa, se ainda
    assim vier vazia/degradada, a resposta é aceita (melhor que travar).
    Erros que não parecem ser de conexão (ex: autenticação, código) são
    relançados imediatamente, sem tentar de novo.
    """
    last_exception: Exception | None = None
    last_bad_response = None

    for attempt in range(max_retries):
        try:
            response = await team.arun(full_input, stream=False, images=images, files=files)
            content = str(response.content) if response and response.content else ""
            is_empty = not content.strip()
            is_degraded = bool(_DEGRADED_FALLBACK_RE.search(content))

            if is_empty or is_degraded:
                last_bad_response = response
                reason = "resposta vazia (falha silenciosa do Agno)" if is_empty else "agentes especializados indisponíveis"
                if attempt == max_retries - 1:
                    # Esgotou as tentativas com a Claude — segue para o
                    # fallback do Gemini abaixo, em vez de aceitar direto.
                    break
                wait = base_delay * (2 ** attempt)
                logger.warning(
                    f"Falha na chamada ao Team — {reason} "
                    f"(tentativa {attempt + 1}/{max_retries}), "
                    f"tentando novamente em {wait:.1f}s"
                )
                await asyncio.sleep(wait)
                continue

            return response

        except Exception as e:
            last_exception = e
            is_retryable = any(kw in str(e).lower() for kw in _RETRYABLE_ERROR_KEYWORDS)
            if not is_retryable or attempt == max_retries - 1:
                # Erro não recuperável tentando de novo com a Claude — mas
                # ainda vale tentar o Gemini abaixo antes de desistir, já
                # que é um provedor totalmente independente (não sofre do
                # mesmo problema, seja ele de conexão ou outro motivo).
                break
            wait = base_delay * (2 ** attempt)
            logger.warning(
                f"Erro de conexão com a API da Anthropic "
                f"(tentativa {attempt + 1}/{max_retries}), "
                f"tentando novamente em {wait:.1f}s: {e}"
            )
            await asyncio.sleep(wait)

    # Todas as tentativas com a Claude falharam (ou o erro não era
    # recuperável) — tenta o provedor de apoio (Gemini) uma vez antes de
    # aceitar uma resposta ruim ou desistir de vez. Esse ponto agora é
    # alcançado por QUALQUER caminho de falha acima (exceção retryable
    # esgotada, exceção não-retryable, conteúdo vazio, ou degradado).
    fallback_content = await _call_fallback_provider(original_message) if original_message else None
    if fallback_content:
        logger.warning("Usando resposta do provedor de apoio (Gemini) apos falha da Claude.")

        class _FallbackResponse:
            content = fallback_content

        return _FallbackResponse()

    if last_bad_response is not None:
        return last_bad_response
    raise last_exception


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
                create_file_editor_agent(student_id),
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

    async def process_message(self, message: str, attachment: Optional[dict] = None) -> dict:
        """Resposta completa — usa stream=False para resposta limpa e sem duplicatas."""
        start = time.time()
        images, files, extra_text = _prepare_attachment(attachment)
        full_message = message + (extra_text or "")
        full_input = f"[student_id={self.student_id}] [session_id={self.session_id}]\n\n{full_message}"
        try:
            response = await _arun_with_retry(self.team, full_input, images, files, original_message=message)
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

    async def process_message_stream(
        self, message: str, attachment: Optional[dict] = None
    ) -> AsyncGenerator[str, None]:
        """
        Coleta toda a resposta do Team e entrega como chunk único limpo.
        O Team no modo coordinate não faz streaming real token a token —
        ele processa agentes internamente e emite a resposta final completa.
        Tentativas de extrair deltas geram texto corrompido.

        Se um anexo (imagem, PDF ou arquivo de texto/código) for informado,
        ele é convertido para o formato multimodal do Agno e enviado junto
        com a mensagem — imagens e PDFs vão nativamente para o modelo,
        texto/código é injetado diretamente no prompt.
        """
        images, files, extra_text = _prepare_attachment(attachment)
        full_message = message + (extra_text or "")
        full_input = f"[student_id={self.student_id}] [session_id={self.session_id}]\n\n{full_message}"
        try:
            # stream=False retorna a resposta completa e limpa
            response = await _arun_with_retry(self.team, full_input, images, files, original_message=message)
            raw_content = response.content if response and response.content else ""
            content = clean_response(str(raw_content))
            if not content:
                yield "*(sem resposta)*"
                return

            # Simula streaming dividindo a resposta em pedaços de ~15 chars
            # para manter o efeito visual de digitação no frontend
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
