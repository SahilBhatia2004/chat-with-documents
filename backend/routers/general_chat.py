import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db
from models.user import User
from models.chat import Chat, ChatMessage
from middleware.auth_middleware import get_current_user
from services.ollama_service import generate_response_stream, generate_chat_title

router = APIRouter(prefix="/api/chat/general", tags=["general-chat"])


class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Chat"


class SendMessageRequest(BaseModel):
    content: str


class RenameChatRequest(BaseModel):
    title: str


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    id: int
    title: str
    chat_type: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ChatDetailResponse(BaseModel):
    id: int
    title: str
    chat_type: str
    created_at: str
    messages: List[dict]

    class Config:
        from_attributes = True


@router.post("")
def create_chat(
    req: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = Chat(user_id=current_user.id, title=req.title, chat_type="general")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return {"id": chat.id, "title": chat.title, "chat_type": chat.chat_type, "created_at": str(chat.created_at)}


@router.get("")
def list_chats(
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Chat).filter(
        Chat.user_id == current_user.id,
        Chat.chat_type == "general"
    )
    if search:
        query = query.filter(Chat.title.ilike(f"%{search}%"))
    chats = query.order_by(Chat.updated_at.desc()).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "chat_type": c.chat_type,
            "created_at": str(c.created_at),
            "updated_at": str(c.updated_at)
        }
        for c in chats
    ]


@router.get("/{chat_id}")
def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": str(m.created_at)
        }
        for m in chat.messages
    ]
    return {
        "id": chat.id,
        "title": chat.title,
        "chat_type": chat.chat_type,
        "created_at": str(chat.created_at),
        "messages": messages
    }


@router.post("/{chat_id}/message")
async def send_message(
    chat_id: int,
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Save user message
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=req.content)
    db.add(user_msg)
    db.commit()

    # Auto-generate title from first message
    msg_count = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).count()
    if msg_count == 1:
        try:
            new_title = await generate_chat_title(req.content)
            chat.title = new_title
            db.commit()
        except Exception:
            pass

    # Build message history for LLM
    messages_for_llm = [
        {"role": "system", "content": "You are a helpful AI assistant for defense personnel. Provide clear, concise, and accurate responses. You operate in an airgapped environment with no internet access."}
    ]
    for msg in chat.messages:
        messages_for_llm.append({"role": msg.role, "content": msg.content})

    # Stream response
    async def event_stream():
        full_response = ""
        async for chunk in generate_response_stream(messages_for_llm):
            full_response += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"

        # Save assistant response
        assistant_msg = ChatMessage(chat_id=chat_id, role="assistant", content=full_response)
        db.add(assistant_msg)
        db.commit()

        yield f"data: {json.dumps({'done': True, 'message_id': assistant_msg.id, 'title': chat.title})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.put("/{chat_id}")
def rename_chat(
    chat_id: int,
    req: RenameChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat.title = req.title
    db.commit()
    return {"id": chat.id, "title": chat.title}


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    db.delete(chat)
    db.commit()
    return {"message": "Chat deleted successfully"}