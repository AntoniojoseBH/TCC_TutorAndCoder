from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete as _delete
from backend.db.models import ChatSession as _ChatSession
import json
import uuid
import asyncio

from backend.db.connection import get_db, redis_client
from backend.db.models import Student
from backend.api.schemas import ChatRequest, ChatResponse
from backend.api.routes.auth import get_current_student
from backend.agents.orchestrator import build_orchestrator

router = APIRouter()

# Intervalo de keep-alive para evitar que o cliente feche a conexão durante
# operações longas do FileEditorAgent ou do LLM
KEEPALIVE_INTERVAL = 15  # segundos


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Resposta completa sem streaming."""
    session_id = request.session_id or str(uuid.uuid4())
    orchestrator = await build_orchestrator(current_student.id, session_id, db, redis_client)
    attachment = request.attachment.dict() if getattr(request, "attachment", None) else None
    result = await orchestrator.process_message(request.message, attachment=attachment)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Erro interno"))

    return ChatResponse(
        content=result["content"],
        session_id=session_id,
        response_time_ms=result["response_time_ms"],
    )


@router.post("/stream")
async def stream_message(
    request: ChatRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    Streaming via Server-Sent Events.
    Envia keep-alive a cada 15s para evitar timeout em operações longas
    como edição de múltiplos arquivos ou geração de projetos completos.
    """
    session_id = request.session_id or str(uuid.uuid4())
    orchestrator = await build_orchestrator(current_student.id, session_id, db, redis_client)

    async def event_generator():
        # Envia session_id como primeiro evento
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        # Processa a mensagem em background enquanto envia keep-alives
        response_chunks = []
        stream_done = False
        stream_error = None

        attachment = request.attachment.dict() if getattr(request, "attachment", None) else None

        async def collect_stream():
            nonlocal stream_done, stream_error
            try:
                async for chunk in orchestrator.process_message_stream(request.message, attachment=attachment):
                    response_chunks.append(chunk)
            except Exception as e:
                stream_error = str(e)
            finally:
                stream_done = True

        # Inicia o streaming em background
        task = asyncio.create_task(collect_stream())

        last_sent = 0
        keepalive_counter = 0

        while not stream_done or last_sent < len(response_chunks):
            # Envia chunks acumulados
            while last_sent < len(response_chunks):
                chunk = response_chunks[last_sent]
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                last_sent += 1
                keepalive_counter = 0  # reseta contador ao enviar conteúdo real

            if not stream_done:
                # Aguarda um pouco antes de checar novamente
                await asyncio.sleep(0.3)
                keepalive_counter += 1

                # Envia keep-alive a cada ~15 segundos (50 * 0.3s = 15s)
                if keepalive_counter >= 50:
                    yield ": keep-alive\n\n"  # comentário SSE — não aparece no frontend
                    keepalive_counter = 0

        if stream_error:
            error_msg = f"\n\n⚠️ Erro: {stream_error}"
            yield f"data: {json.dumps({'type': 'chunk', 'content': error_msg})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/history/{session_id}")
async def get_session_history(
    session_id: str,
    current_student: Student = Depends(get_current_student),
):
    """Retorna o histórico de uma sessão de chat."""
    session_key = f"session:{session_id}"
    data = await redis_client.get(session_key)
    if not data:
        return {"history": [], "session_id": session_id}
    return {"history": json.loads(data), "session_id": session_id}


@router.get("/sessions")
async def get_all_sessions(
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Retorna todas as sessões do estudante com data e prévia da primeira mensagem."""
    from sqlalchemy import select, func
    from backend.db.models import Interaction

    # Busca sessões únicas com data e primeira mensagem
    result = await db.execute(
        select(
            Interaction.session_id,
            func.min(Interaction.timestamp).label("started_at"),
            func.count(Interaction.id).label("message_count"),
        )
        .where(Interaction.student_id == current_student.id)
        .group_by(Interaction.session_id)
        .order_by(func.min(Interaction.timestamp).desc())
        .limit(20)
    )
    sessions = []
    for row in result.all():
        # Busca a primeira mensagem do usuário para usar como título
        first_msg = await db.execute(
            select(Interaction.content)
            .where(Interaction.student_id == current_student.id)
            .where(Interaction.session_id == row.session_id)
            .where(Interaction.role == "user")
            .order_by(Interaction.timestamp)
            .limit(1)
        )
        first_content = first_msg.scalar_one_or_none() or "Nova conversa"

        # Usa nome customizado do PostgreSQL se existir (persiste entre reinícios)
        from sqlalchemy import select as _select
        from backend.db.models import ChatSession as _ChatSession

        custom_result = await db.execute(
            _select(_ChatSession.custom_name).where(_ChatSession.session_id == row.session_id)
        )
        custom_name = custom_result.scalar_one_or_none()

        title = custom_name if custom_name else (
            first_content[:50] + ("..." if len(first_content) > 50 else "")
        )
        sessions.append({
            "session_id": row.session_id,
            "started_at": row.started_at.strftime("%d/%m/%Y %H:%M"),
            "message_count": row.message_count,
            "title": title,
            "preview": first_content[:60] + ("..." if len(first_content) > 60 else ""),
        })
    return {"sessions": sessions}


@router.patch("/session/{session_id}/rename")
async def rename_session(
    session_id: str,
    request: dict,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    new_name = request.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Nome não pode ser vazio")

    from sqlalchemy import select
    from backend.db.models import ChatSession

    result = await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )
    session_row = result.scalar_one_or_none()

    if session_row:
        session_row.custom_name = new_name[:80]
    else:
        session_row = ChatSession(
            session_id=session_id,
            student_id=current_student.id,
            custom_name=new_name[:80],
        )
        db.add(session_row)

    await db.commit()
    return {"ok": True}

@router.delete("/session-full/{session_id}")
async def delete_session_full(
    session_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Deleta completamente uma sessão (Redis + PostgreSQL)."""
    from sqlalchemy import delete as sql_delete
    from backend.db.models import Interaction
    await db.execute(
        sql_delete(Interaction)
        .where(Interaction.student_id == current_student.id)
        .where(Interaction.session_id == session_id)
    )

    await db.execute(_delete(_ChatSession).where(_ChatSession.session_id == session_id))
    await db.commit()
    await redis_client.delete(f"session:{session_id}")
    return {"ok": True}


@router.get("/history-db/{session_id}")
async def get_session_history_from_db(
    session_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Retorna o histórico completo de uma sessão diretamente do PostgreSQL."""
    from sqlalchemy import select
    from backend.db.models import Interaction

    result = await db.execute(
        select(Interaction.role, Interaction.content, Interaction.timestamp)
        .where(Interaction.student_id == current_student.id)
        .where(Interaction.session_id == session_id)
        .where(Interaction.role.in_(["user", "assistant"]))
        .order_by(Interaction.timestamp)
    )
    messages = [
        {"role": row.role, "content": row.content}
        for row in result.all()
    ]
    return {"messages": messages, "session_id": session_id}


@router.post("/save-message")
async def save_message(
    request: dict,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Salva uma mensagem no banco com conteúdo completo e tempo de resposta."""
    from backend.db.models import Interaction
    session_id = request.get("session_id", "")
    role = request.get("role", "assistant")
    content = request.get("content", "")
    response_time_ms = request.get("response_time_ms")
    if not content or not session_id:
        return {"ok": False}
    interaction = Interaction(
        student_id=current_student.id,
        session_id=session_id,
        role=role,
        content=content,
        intent="conversation",
        response_time_ms=response_time_ms,
    )
    db.add(interaction)
    await db.commit()
    return {"ok": True}


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    current_student: Student = Depends(get_current_student),
):
    """Limpa o histórico de uma sessão."""
    await redis_client.delete(f"session:{session_id}")
    return {"message": "Sessão limpa com sucesso"}