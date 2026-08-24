from fastapi import APIRouter, Depends, HTTPException
from backend.db.models import Student
from backend.api.schemas import (
    FileReadRequest, FileWriteRequest, FilePatchRequest,
    MultiFileWriteRequest, FileOperationResponse,
)
from backend.api.routes.auth import get_current_student
from backend.tools.file_editor import (
    read_file, write_file, patch_file,
    list_files, write_multiple_files, get_project_summary, delete_file,
)

router = APIRouter()


@router.get("/list")
async def list_student_files(
    directory: str = ".",
    current_student: Student = Depends(get_current_student),
):
    """Lista os arquivos do projeto do estudante."""
    result = list_files(current_student.id, directory)
    return {"files": result.content, "message": result.message}


@router.get("/summary")
async def get_project_summary_route(
    current_student: Student = Depends(get_current_student),
):
    """Retorna o resumo completo do projeto (estrutura + conteúdo)."""
    summary = get_project_summary(current_student.id)
    return {"summary": summary}


@router.post("/read", response_model=FileOperationResponse)
async def read_student_file(
    request: FileReadRequest,
    current_student: Student = Depends(get_current_student),
):
    """Lê um arquivo do projeto do estudante."""
    result = read_file(current_student.id, request.path)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    return FileOperationResponse(success=True, path=result.path, message=result.content or "")


@router.post("/write", response_model=FileOperationResponse)
async def write_student_file(
    request: FileWriteRequest,
    current_student: Student = Depends(get_current_student),
):
    """Cria ou sobrescreve um arquivo do projeto do estudante."""
    result = write_file(current_student.id, request.path, request.content)
    return FileOperationResponse(
        success=result.success,
        path=result.path,
        message=result.message,
        diff=result.diff,
    )


@router.post("/patch", response_model=FileOperationResponse)
async def patch_student_file(
    request: FilePatchRequest,
    current_student: Student = Depends(get_current_student),
):
    """Aplica uma edição cirúrgica em um arquivo."""
    result = patch_file(current_student.id, request.path, request.old_code, request.new_code)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return FileOperationResponse(
        success=True,
        path=result.path,
        message=result.message,
        diff=result.diff,
    )


@router.post("/write-multiple")
async def write_multiple_student_files(
    request: MultiFileWriteRequest,
    current_student: Student = Depends(get_current_student),
):
    """Cria ou atualiza múltiplos arquivos de uma vez."""
    results = write_multiple_files(current_student.id, request.files)
    return {
        "results": [
            {"path": r.path, "success": r.success, "message": r.message, "diff": r.diff}
            for r in results
        ],
        "total_ok": sum(1 for r in results if r.success),
        "total": len(results),
    }


@router.delete("/delete")
async def delete_student_file(
    path: str,
    current_student: Student = Depends(get_current_student),
):
    """Deleta um arquivo do projeto do estudante."""
    result = delete_file(current_student.id, path)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)
    return FileOperationResponse(
        success=True,
        path=result.path,
        message=result.message,
    )


@router.get("/tree")
async def get_file_tree(
    current_student: Student = Depends(get_current_student),
):
    """Retorna árvore de arquivos no formato {projeto: [arquivo1, arquivo2]}."""
    import os
    from backend.config import settings
    from pathlib import Path

    student_root = Path(settings.PROJECTS_ROOT) / current_student.id
    tree = {}

    if not student_root.exists():
        return {"tree": {}}

    for item in sorted(student_root.rglob("*")):
        if item.is_file():
            rel = item.relative_to(student_root)
            parts = rel.parts
            if len(parts) == 1:
                # Arquivo solto na raiz
                if "_root" not in tree:
                    tree["_root"] = []
                tree["_root"].append(parts[0])
            else:
                # Arquivo dentro de pasta (projeto)
                proj = parts[0]
                fname = "/".join(parts[1:])
                if proj not in tree:
                    tree[proj] = []
                tree[proj].append(fname)

    return {"tree": tree}