"""
Agente de Edição de Arquivos

Responsabilidades:
- Ler, criar e editar múltiplos arquivos do projeto do estudante
- Refatorar código em vários arquivos simultaneamente
- Criar estrutura completa de projetos
- Aplicar correções cirúrgicas preservando código existente
- Gerar diffs legíveis de cada alteração
- Analisar dependências entre arquivos e impacto de mudanças

Este agente habilita a funcionalidade de "editar múltiplos arquivos"
que diferencia o sistema de um simples chatbot.
"""

from agno.agent import Agent
from agno.models.anthropic import Claude
from backend.agents._model import get_model
from agno.tools import tool
import json
import re
import logging

from backend.config import settings
from backend.tools.file_editor import (
    read_file,
    write_file,
    patch_file,
    list_files,
    read_multiple_files,
    write_multiple_files,
    get_project_summary,
    PROJECTS_ROOT,
)

logger = logging.getLogger(__name__)


@tool
def tool_read_file(student_id: str, path: str) -> str:
    """Lê um arquivo do projeto do estudante."""
    result = read_file(student_id, path)
    if not result.success:
        return f"ERRO: {result.message}"
    return f"=== {path} ===\n{result.content}"


@tool
def tool_write_file(student_id: str, path: str, content: str) -> str:
    """
    Cria ou sobrescreve um arquivo completo.
    Use quando criar um arquivo novo ou reescrever completamente.
    """
    result = write_file(student_id, path, content)
    if not result.success:
        return f"ERRO: {result.message}"
    response = f"✅ {result.message} → {path}"
    if result.diff and result.diff != "(sem alterações)":
        response += f"\n\nDiff:\n{result.diff}"
    return response


@tool
def tool_patch_file(student_id: str, path: str, old_code: str, new_code: str) -> str:
    """
    Aplica uma edição cirúrgica: substitui 'old_code' por 'new_code' no arquivo.
    PREFERIR este método ao invés de write_file quando apenas parte do arquivo muda.
    old_code deve ser uma cópia EXATA do trecho a ser substituído.
    """
    result = patch_file(student_id, path, old_code, new_code)
    if not result.success:
        return f"ERRO: {result.message}"
    response = f"✅ Patch aplicado em {path}"
    if result.diff:
        response += f"\n\nDiff:\n{result.diff}"
    return response


@tool
def tool_list_files(student_id: str, directory: str = ".") -> str:
    """Lista todos os arquivos do projeto do estudante."""
    result = list_files(student_id, directory)
    return result.content or "(projeto vazio)"


@tool
def tool_read_multiple_files(student_id: str, paths_json: str) -> str:
    """
    Lê múltiplos arquivos de uma vez.
    paths_json: lista JSON de caminhos, ex: '["main.py", "utils.py", "config.py"]'
    Útil para entender o contexto completo antes de editar.
    """
    try:
        paths = json.loads(paths_json)
    except Exception:
        return "ERRO: paths_json deve ser uma lista JSON válida."

    results = read_multiple_files(student_id, paths)
    output_parts = []
    for r in results:
        if r.success:
            output_parts.append(f"=== {r.path} ===\n{r.content}\n")
        else:
            output_parts.append(f"=== {r.path} ===\nERRO: {r.message}\n")
    return "\n".join(output_parts)


@tool
def tool_write_multiple_files(student_id: str, files_json: str) -> str:
    """
    Cria ou atualiza múltiplos arquivos de uma vez.
    files_json: objeto JSON {caminho: conteúdo}.
    Ideal para criar ou refatorar um projeto inteiro em uma operação.

    IMPORTANTE: ao criar um PROJETO, todos os caminhos devem comecar com
    o nome da pasta do projeto, ex: {"calculadora/main.py": "...",
    "calculadora/calculadora.py": "..."}. NUNCA use caminhos soltos na
    raiz (ex: "main.py") quando o pedido for para criar um projeto -
    isso faz os arquivos aparecerem fora de qualquer pasta na interface.
    """
    try:
        files = json.loads(files_json)
    except Exception:
        return "ERRO: files_json deve ser um objeto JSON válido."

    results = write_multiple_files(student_id, files)
    output_parts = []
    total_ok = 0
    for r in results:
        if r.success:
            total_ok += 1
            line = f"✅ {r.path}"
            if r.diff and r.diff != "(sem alterações)":
                line += " (modificado)"
            output_parts.append(line)
        else:
            output_parts.append(f"❌ {r.path}: {r.message}")

    summary = f"\nTotal: {total_ok}/{len(results)} arquivo(s) processado(s) com sucesso."
    return "\n".join(output_parts) + summary


@tool
def tool_get_project_summary(student_id: str) -> str:
    """
    Retorna um resumo completo do projeto: estrutura + conteúdo de todos os arquivos.
    Use ANTES de editar para entender o estado atual do projeto.
    """
    return get_project_summary(student_id)


@tool
def tool_analyze_project_dependencies(student_id: str) -> str:
    """
    Analisa as dependências entre todos os arquivos do projeto.
    Retorna um mapa de quais arquivos importam quais, identificando
    o grafo de dependências completo do projeto.
    Use antes de editar para saber quais arquivos serão afetados por uma mudança.
    """
    base = PROJECTS_ROOT / student_id
    if not base.exists():
        return "Projeto vazio."

    # Lê todos os arquivos de código fonte
    source_files = {}
    for f in sorted(base.rglob("*")):
        if f.is_file() and f.suffix in {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h"}:
            rel = str(f.relative_to(base)).replace("\\", "/")
            try:
                source_files[rel] = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    if not source_files:
        return "Nenhum arquivo de código fonte encontrado."

    # Extrai dependências por linguagem
    dependency_map = {}

    for filename, content in source_files.items():
        deps = []
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

        if ext == "py":
            # Captura: import X, from X import Y, from .X import Y
            imports = re.findall(
                r'^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))',
                content, re.MULTILINE
            )
            for imp in imports:
                module = (imp[0] or imp[1]).strip()
                # Verifica se o módulo é um arquivo local do projeto
                module_path = module.replace(".", "/")
                for candidate in [f"{module_path}.py", f"{module_path}/__init__.py"]:
                    if candidate in source_files:
                        deps.append(candidate)
                        break
                # Trata imports relativos (from . import X)
                if module.startswith("."):
                    clean = module.lstrip(".")
                    candidate = clean.replace(".", "/") + ".py"
                    if candidate in source_files:
                        deps.append(candidate)

        elif ext in {"js", "ts"}:
            # Captura: import X from './X', require('./X')
            imports = re.findall(
                r'''(?:import\s+.*?from\s+|require\s*\(\s*)['"](\./[^'"]+)['"]''',
                content
            )
            for imp in imports:
                imp_clean = imp.lstrip("./")
                for candidate in [f"{imp_clean}.js", f"{imp_clean}.ts", imp_clean]:
                    if candidate in source_files:
                        deps.append(candidate)
                        break

        elif ext == "java":
            # Captura: import com.example.Classe
            imports = re.findall(r'^\s*import\s+([\w\.]+);', content, re.MULTILINE)
            for imp in imports:
                parts = imp.split(".")
                candidate = "/".join(parts) + ".java"
                if candidate in source_files:
                    deps.append(candidate)

        dependency_map[filename] = list(set(deps))

    # Monta relatório de dependências
    lines = ["=== MAPA DE DEPENDÊNCIAS DO PROJETO ===\n"]

    # Quais arquivos cada arquivo depende
    lines.append("📦 Dependências diretas (arquivo → o que importa):")
    has_deps = False
    for fname, deps in dependency_map.items():
        if deps:
            has_deps = True
            lines.append(f"  {fname}")
            for d in deps:
                lines.append(f"    └─ importa: {d}")
    if not has_deps:
        lines.append("  Nenhuma dependência local detectada.")

    # Grafo reverso: quem depende de cada arquivo
    lines.append("\n🔗 Impacto reverso (arquivo → quem o importa):")
    reverse_map = {f: [] for f in source_files}
    for fname, deps in dependency_map.items():
        for dep in deps:
            if dep in reverse_map:
                reverse_map[dep].append(fname)

    has_reverse = False
    for fname, dependents in reverse_map.items():
        if dependents:
            has_reverse = True
            lines.append(f"  {fname}")
            for d in dependents:
                lines.append(f"    └─ usado por: {d}")
    if not has_reverse:
        lines.append("  Nenhuma dependência local detectada.")

    # Arquivos isolados (sem dependências e sem dependentes)
    isolated = [
        f for f in source_files
        if not dependency_map.get(f) and not reverse_map.get(f)
    ]
    if isolated:
        lines.append(f"\n⚪ Arquivos independentes (sem dependências locais):")
        for f in isolated:
            lines.append(f"  {f}")

    return "\n".join(lines)


@tool
def tool_check_impact(student_id: str, changed_file: str, changes_description: str) -> str:
    """
    Verifica o impacto de uma mudança em um arquivo específico sobre os demais arquivos do projeto.

    Parâmetros:
    - changed_file: caminho do arquivo que será modificado (ex: 'calculadora.py')
    - changes_description: descrição das mudanças planejadas (ex: 'renomear função soma para somar, adicionar parâmetro c')

    Retorna lista de arquivos afetados e o que precisará ser ajustado em cada um.
    """
    base = PROJECTS_ROOT / student_id
    if not base.exists():
        return "Projeto vazio."

    # Lê o arquivo que será alterado
    changed_result = read_file(student_id, changed_file)
    if not changed_result.success:
        return f"Arquivo '{changed_file}' não encontrado."

    changed_content = changed_result.content

    # Lê todos os outros arquivos para verificar dependências
    source_files = {}
    for f in sorted(base.rglob("*")):
        if f.is_file() and f.suffix in {".py", ".js", ".ts", ".java", ".c", ".cpp"}:
            rel = str(f.relative_to(base)).replace("\\", "/")
            if rel != changed_file:
                try:
                    source_files[rel] = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    if not source_files:
        return f"Apenas '{changed_file}' existe no projeto — sem outros arquivos para verificar."

    # Extrai símbolos exportados pelo arquivo alterado (funções, classes, variáveis)
    exported_symbols = []
    ext = changed_file.rsplit(".", 1)[-1] if "." in changed_file else ""

    if ext == "py":
        # Funções e classes definidas no nível superior
        symbols = re.findall(r'^(?:def|class)\s+(\w+)', changed_content, re.MULTILINE)
        exported_symbols.extend(symbols)
        # Constantes (variáveis em MAIÚSCULAS)
        constants = re.findall(r'^([A-Z_]{2,})\s*=', changed_content, re.MULTILINE)
        exported_symbols.extend(constants)

    elif ext in {"js", "ts"}:
        symbols = re.findall(r'(?:export\s+(?:function|class|const|let)\s+)(\w+)', changed_content)
        exported_symbols.extend(symbols)

    elif ext == "java":
        symbols = re.findall(r'(?:public|protected)\s+(?:class|interface|void|\w+)\s+(\w+)', changed_content)
        exported_symbols.extend(symbols)

    # Verifica quais outros arquivos referenciam o arquivo alterado ou seus símbolos
    module_name = changed_file.replace("/", ".").rsplit(".", 1)[0]  # ex: calculadora.py → calculadora
    affected = {}

    for fname, fcontent in source_files.items():
        issues = []

        # Verifica se o arquivo importa o módulo alterado
        imports_module = (
            module_name in fcontent or
            changed_file.rsplit(".", 1)[0] in fcontent
        )

        if imports_module:
            # Verifica quais símbolos do arquivo alterado são usados
            for symbol in exported_symbols:
                if symbol in fcontent:
                    # Conta as ocorrências de uso
                    occurrences = len(re.findall(rf'\b{re.escape(symbol)}\b', fcontent))
                    issues.append(f"usa '{symbol}' ({occurrences}x)")

            if issues:
                affected[fname] = issues
            else:
                affected[fname] = ["importa o módulo (verificar manualmente)"]

    # Monta relatório de impacto
    lines = [
        f"=== ANÁLISE DE IMPACTO: {changed_file} ===",
        f"Mudanças planejadas: {changes_description}",
        f"Símbolos exportados detectados: {', '.join(exported_symbols) if exported_symbols else 'nenhum'}",
        "",
    ]

    if affected:
        lines.append(f"⚠️  {len(affected)} arquivo(s) AFETADO(S):\n")
        for fname, issues in affected.items():
            lines.append(f"  📄 {fname}")
            for issue in issues:
                lines.append(f"     → {issue}")
            lines.append("")
        lines.append("💡 Ação recomendada: atualize os arquivos afetados após modificar o arquivo principal.")
    else:
        lines.append("✅ Nenhum outro arquivo será afetado por esta mudança.")

    return "\n".join(lines)


def create_file_editor_agent() -> Agent:
    return Agent(
        name="FileEditorAgent",
        role="Agente de Edição de Múltiplos Arquivos",
        model=get_model(settings.LLM_MODEL),
        tools=[
            tool_read_file,
            tool_write_file,
            tool_patch_file,
            tool_list_files,
            tool_read_multiple_files,
            tool_write_multiple_files,
            tool_get_project_summary,
            tool_analyze_project_dependencies,
            tool_check_impact,
        ],
        instructions=[
            "Você edita projetos de código com precisão cirúrgica e consciência das dependências.",
            "",
            "ESTRUTURA DE PASTAS — REGRA CRÍTICA E OBRIGATÓRIA:",
            "  - Quando o estudante pedir para CRIAR UM PROJETO (ex: 'crie um projeto de calculadora',",
            "    'crie um projeto Flask', 'projeto de lista de tarefas'), TODOS os arquivos desse",
            "    projeto DEVEM ficar dentro de uma pasta com o nome do projeto.",
            "  - O caminho de cada arquivo deve ser 'nome_do_projeto/arquivo.ext', nunca apenas",
            "    'arquivo.ext' na raiz.",
            "  - Escolha um nome de pasta curto, em snake_case, sem espaços e sem acentos,",
            "    derivado do que o estudante descreveu (ex: 'calculadora', 'todo_list', 'api_flask').",
            "  - Exemplo CORRETO: pedido 'crie um projeto de calculadora com main.py e calculadora.py'",
            "    → tool_write_multiple_files com paths: 'calculadora/main.py', 'calculadora/calculadora.py'",
            "  - Exemplo ERRADO: usar os paths 'main.py', 'calculadora.py' direto na raiz — isso faz",
            "    os arquivos aparecerem como soltos, sem agrupamento de projeto.",
            "  - Essa regra NÃO se aplica quando o estudante pede para criar UM ÚNICO arquivo solto",
            "    (ex: 'crie um arquivo utils.py') ou editar um arquivo já existente — nesses casos",
            "    use o caminho exatamente como já está ou como o estudante indicar.",
            "",
            "PROTOCOLO OBRIGATÓRIO antes de qualquer edição:",
            "  1. Use tool_get_project_summary para entender o projeto completo.",
            "  2. Use tool_analyze_project_dependencies para mapear as dependências entre arquivos.",
            "  3. Use tool_check_impact para verificar quais arquivos serão afetados pela mudança.",
            "  4. Planeje TODAS as mudanças necessárias em todos os arquivos afetados.",
            "  5. Execute as edições na ordem correta (dependências primeiro).",
            "",
            "REGRAS DE EDIÇÃO:",
            "  - Prefira tool_patch_file quando apenas PARTE de um arquivo muda.",
            "  - Use tool_write_file para arquivos novos ou reescritas completas.",
            "  - Use tool_write_multiple_files para criar projetos do zero.",
            "  - NUNCA edite apenas um arquivo se a mudança afeta outros — edite todos.",
            "  - Preserve sempre o código existente que não precisa mudar.",
            "",
            "ANÁLISE DE IMPACTO — ative automaticamente quando o estudante:",
            "  - Renomear uma função, classe ou variável exportada",
            "  - Alterar a assinatura (parâmetros) de uma função",
            "  - Mover código entre arquivos",
            "  - Remover ou deprecar uma função/classe",
            "  - Alterar o nome de um arquivo que é importado por outros",
            "",
            "APÓS CADA EDIÇÃO COORDENADA:",
            "  - Mostre o diff de cada arquivo modificado.",
            "  - Explique por que cada arquivo precisou ser atualizado.",
            "  - Liste os arquivos modificados em ordem.",
            "  - Indique se o estudante precisa instalar dependências.",
            "",
            "EXEMPLOS DE EDIÇÃO COORDENADA:",
            "  - Renomear 'soma' para 'somar' em calculadora.py:",
            "    → Atualiza calculadora.py (define a função)",
            "    → Atualiza main.py (chama a função)",
            "    → Atualiza testes.py (testa a função)",
            "  - Adicionar parâmetro obrigatório a uma função:",
            "    → Atualiza o arquivo da função",
            "    → Atualiza todos os arquivos que a chamam",
            "  - Mover classe para novo arquivo:",
            "    → Cria o novo arquivo",
            "    → Remove do arquivo original",
            "    → Atualiza todos os imports",
        ],
    )