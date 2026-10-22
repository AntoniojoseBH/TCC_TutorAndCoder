"""
Ferramenta de edição de arquivos para a IA Agêntica.
"""

import os
import re
import difflib
from pathlib import Path
from dataclasses import dataclass
from typing import Literal
import logging

logger = logging.getLogger(__name__)

# Diretório raiz — resolve() garante caminho absoluto com drive letter no Windows
PROJECTS_ROOT = Path(os.getenv("PROJECTS_ROOT", "/tmp/student_projects")).resolve()


@dataclass
class FileOperation:
    operation: Literal["read", "write", "patch", "list", "delete"]
    path: str
    content: str | None = None
    patch: str | None = None


@dataclass
class FileResult:
    success: bool
    path: str
    content: str | None
    message: str
    diff: str | None = None


def _resolve_path(student_id: str, relative_path: str) -> Path:
    """Resolve o caminho do arquivo dentro do sandbox do estudante."""
    base = (PROJECTS_ROOT / student_id).resolve()
    base.mkdir(parents=True, exist_ok=True)
    # resolve() garante que ambos os caminhos têm o mesmo formato (com drive no Windows)
    resolved = (base / relative_path).resolve()
    base_str = str(base)
    resolved_str = str(resolved)
    # Comparação case-insensitive no Windows
    if os.name == "nt":
        check = resolved_str.lower().startswith(base_str.lower())
    else:
        check = resolved_str.startswith(base_str)
    if not check:
        raise PermissionError(f"Acesso negado: caminho fora do sandbox — {relative_path}")
    return resolved


def read_file(student_id: str, path: str) -> FileResult:
    """Lê o conteúdo de um arquivo do projeto do estudante."""
    try:
        full_path = _resolve_path(student_id, path)
        if not full_path.exists():
            return FileResult(success=False, path=path, content=None, message=f"Arquivo não encontrado: {path}")
        content = full_path.read_text(encoding="utf-8")
        return FileResult(success=True, path=path, content=content, message="Arquivo lido com sucesso.")
    except Exception as e:
        return FileResult(success=False, path=path, content=None, message=str(e))


def write_file(student_id: str, path: str, content: str) -> FileResult:
    """Cria ou sobrescreve um arquivo no projeto do estudante."""
    try:
        full_path = _resolve_path(student_id, path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        old_content = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
        diff = _generate_diff(old_content, content, path)
        full_path.write_text(content, encoding="utf-8")
        action = "atualizado" if old_content else "criado"
        return FileResult(success=True, path=path, content=content, message=f"Arquivo {action} com sucesso.", diff=diff)
    except Exception as e:
        return FileResult(success=False, path=path, content=None, message=str(e))


def patch_file(student_id: str, path: str, old_code: str, new_code: str) -> FileResult:
    """Aplica edição cirúrgica substituindo old_code por new_code."""
    try:
        full_path = _resolve_path(student_id, path)
        if not full_path.exists():
            return FileResult(success=False, path=path, content=None, message=f"Arquivo não encontrado: {path}")
        original = full_path.read_text(encoding="utf-8")
        if old_code not in original:
            return FileResult(success=False, path=path, content=original,
                              message="Trecho não encontrado no arquivo.")
        updated = original.replace(old_code, new_code, 1)
        diff = _generate_diff(original, updated, path)
        full_path.write_text(updated, encoding="utf-8")
        return FileResult(success=True, path=path, content=updated, message="Patch aplicado com sucesso.", diff=diff)
    except Exception as e:
        return FileResult(success=False, path=path, content=None, message=str(e))


def list_files(student_id: str, directory: str = ".") -> FileResult:
    """Lista todos os arquivos de um diretório do projeto."""
    try:
        full_path = _resolve_path(student_id, directory)
        if not full_path.exists():
            return FileResult(success=True, path=directory, content="(projeto vazio)", message="")
        files = []
        for f in sorted(full_path.rglob("*")):
            if f.is_file():
                rel = f.relative_to(PROJECTS_ROOT / student_id)
                # Usa forward slash para compatibilidade entre OS
                rel_str = str(rel).replace("\\", "/")
                size = f.stat().st_size
                files.append(f"{rel_str}  ({size} bytes)")
        content = "\n".join(files) if files else "(projeto vazio)"
        return FileResult(success=True, path=directory, content=content,
                          message=f"{len(files)} arquivo(s) encontrado(s).")
    except Exception as e:
        return FileResult(success=False, path=directory, content=None, message=str(e))


def read_multiple_files(student_id: str, paths: list[str]) -> list[FileResult]:
    return [read_file(student_id, path) for path in paths]


def write_multiple_files(student_id: str, files: dict[str, str]) -> list[FileResult]:
    results = []
    for path, content in files.items():
        result = write_file(student_id, path, content)
        results.append(result)
    return results


def get_project_summary(student_id: str, project: str | None = None) -> str:
    """
    Monta um resumo textual do projeto para análise pela IA.

    IMPORTANTE: se "project" for informado, o resumo é restrito SOMENTE
    aos arquivos daquele projeto (subpasta) — nunca varre o workspace
    inteiro do estudante. Sem isso, a análise mistura arquivos de todos
    os projetos que o estudante já criou num único relatório, o que é
    incorreto e confunde o resultado apresentado ao usuário.
    """
    workspace_root = PROJECTS_ROOT / student_id

    if project and project != "_root":
        base = workspace_root / project
    else:
        base = workspace_root

    if not base.exists():
        return "Projeto vazio — nenhum arquivo ainda."

    summary_parts = ["=== ESTRUTURA DO PROJETO ==="]
    file_list = list_files(student_id, directory=project if project and project != "_root" else ".")
    summary_parts.append(file_list.content or "(vazio)")
    summary_parts.append("\n=== CONTEÚDO DOS ARQUIVOS ===")
    for f in sorted(base.rglob("*")):
        if f.is_file() and f.suffix in {".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt"}:
            rel = str(f.relative_to(base)).replace("\\", "/")
            content = f.read_text(encoding="utf-8", errors="replace")
            summary_parts.append(f"\n--- {rel} ---\n{content}")
    return "\n".join(summary_parts)


def delete_file(student_id: str, path: str) -> FileResult:
    """Deleta um arquivo do projeto do estudante."""
    try:
        full_path = _resolve_path(student_id, path)
        if not full_path.exists():
            return FileResult(success=False, path=path, content=None,
                              message=f"Arquivo não encontrado: {path}")
        full_path.unlink()
        # Remove diretório pai se ficou vazio
        parent = full_path.parent
        base = (PROJECTS_ROOT / student_id).resolve()
        if parent != base and not any(parent.iterdir()):
            parent.rmdir()
        return FileResult(success=True, path=path, content=None,
                          message=f"Arquivo '{path}' deletado com sucesso.")
    except Exception as e:
        return FileResult(success=False, path=path, content=None, message=str(e))


def _generate_diff(old: str, new: str, filename: str) -> str:
    if old == new:
        return "(sem alterações)"
    diff_lines = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    ))
    return "".join(diff_lines[:80])