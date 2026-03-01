import os
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from models.user import User
from models.chat import Chat, ChatMessage
from models.document import DocumentUpload, FAISSMapping
from middleware.auth_middleware import get_current_user
from services.document_service import convert_to_pdf, extract_content
from services.chunking_service import chunk_text
from services.vector_service import create_faiss_index, search_faiss_index
from services.ollama_service import generate_response_stream, generate_chat_title
from services.cleanup_service import cleanup_chat_assets, cleanup_document_assets
from config import DOCUMENTS_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/policy", tags=["policy-chat"])

class SendMessageRequest(BaseModel):
    content: str
    upload_timestamp: Optional[str] = None

class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Internal Policies Chat"

@router.post("")
def create_chat(
    req: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = Chat(user_id=current_user.id, title=req.title, chat_type="policy")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return {
        "id": chat.id, "title": chat.title,
        "chat_type": chat.chat_type, "created_at": str(chat.created_at)
    }

@router.get("")
def list_chats(
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Chat).filter(
        Chat.user_id == current_user.id,
        Chat.chat_type == "policy"
    )
    if search:
        query = query.filter(Chat.title.ilike(f"%{search}%"))
    chats = query.order_by(Chat.updated_at.desc()).all()
    return [
        {
            "id": c.id, "title": c.title,
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
            "id": m.id, "role": m.role, "content": m.content,
            "created_at": str(m.created_at)
        }
        for m in chat.messages
    ]

    uploads = db.query(DocumentUpload).filter(DocumentUpload.chat_id == chat_id).all()
    upload_info = [
        {
            "id": u.id, "filename": u.filename,
            "upload_timestamp": u.upload_timestamp,
            "created_at": str(u.created_at)
        }
        for u in uploads
    ]

    return {
        "id": chat.id, "title": chat.title,
        "chat_type": chat.chat_type, "created_at": str(chat.created_at),
        "messages": messages, "uploads": upload_info
    }

@router.post("/{chat_id}/upload")
async def upload_policy(
    chat_id: int,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    upload_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    upload_dir = os.path.join(DOCUMENTS_DIR, str(chat_id), upload_timestamp)
    os.makedirs(upload_dir, exist_ok=True)

    all_text = ""
    processed_files = []

    for file in files:
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        try:
            pdf_path = convert_to_pdf(file_path)
            extracted = extract_content(pdf_path)
            all_text += f"\n\n--- {file.filename} ---\n\n" + extracted["text_content"]

            doc_upload = DocumentUpload(
                chat_id=chat_id, user_id=current_user.id,
                filename=file.filename, upload_timestamp=upload_timestamp,
                pdf_path=pdf_path
            )
            db.add(doc_upload)
            processed_files.append(file.filename)
        except Exception as e:
            logger.error(f"Policy extraction error for {file.filename}: {e}")

    faiss_created = False
    if all_text.strip():
        chunks = chunk_text(all_text)
        if chunks:
            index_path, chunks_path = create_faiss_index(
                chunks, chat_id, current_user.id, upload_timestamp
            )
            faiss_mapping = FAISSMapping(
                chat_id=chat_id, user_id=current_user.id,
                upload_timestamp=upload_timestamp,
                faiss_index_path=index_path, chunks_path=chunks_path
            )
            db.add(faiss_mapping)
            faiss_created = True

    db.commit()

    if processed_files:
        upload_count = db.query(DocumentUpload).filter(DocumentUpload.chat_id == chat_id).count()
        if upload_count == len(processed_files):
            try:
                new_title = await generate_chat_title(f"Policy study: {processed_files[0]}")
                chat.title = new_title
                db.commit()
            except Exception: pass

        sys_content = f"🛡️ Uploaded {len(processed_files)} policy document(s): {', '.join(processed_files)}."
        if faiss_created:
            sys_content += " Indexed for semantic policy search."
        sys_msg = ChatMessage(chat_id=chat_id, role="assistant", content=sys_content)
        db.add(sys_msg)
        db.commit()

    return {
        "message": "Policy documents processed successfully",
        "upload_timestamp": upload_timestamp,
        "files_processed": processed_files,
        "text_indexed": faiss_created,
        "chat_title": chat.title
    }

@router.delete("/{chat_id}/document/{document_id}")
def delete_policy_document(
    chat_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify ownership
    doc = db.query(DocumentUpload).filter(
        DocumentUpload.id == document_id,
        DocumentUpload.chat_id == chat_id,
        DocumentUpload.user_id == current_user.id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied")
    
    cleanup_document_assets(document_id, db)
    return {"message": "Document and all related assets deleted"}

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

    user_msg = ChatMessage(chat_id=chat_id, role="user", content=req.content)
    db.add(user_msg)
    db.commit()

    # Search context from all FAISS indexes in this chat
    faiss_mappings = db.query(FAISSMapping).filter(
        FAISSMapping.chat_id == chat_id,
        FAISSMapping.user_id == current_user.id
    ).all()

    faiss_context = ""
    # If a specific timestamp is given, only use that. Otherwise, use ALL for global policy search
    active_timestamp = req.upload_timestamp
    if active_timestamp:
        faiss_mappings = [m for m in faiss_mappings if m.upload_timestamp == active_timestamp]

    all_results = []
    for fm in faiss_mappings:
        try:
            results = search_faiss_index(req.content, fm.faiss_index_path, fm.chunks_path, top_k=3)
            all_results.extend(results)
        except Exception: pass

    # Sort and take top
    all_results.sort(key=lambda x: x["score"])
    faiss_context = "\n\n".join([r["chunk"]["text"] for r in all_results[:5]])

    async def response_stream():
        from routers.document_chat import _build_llm_messages
        messages_for_llm = _build_llm_messages(chat, faiss_context, None, req.content, db)
        
        full_response = ""
        async for chunk in generate_response_stream(messages_for_llm):
            full_response += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"

        assistant_msg = ChatMessage(chat_id=chat_id, role="assistant", content=full_response)
        db.add(assistant_msg)
        db.commit()
        yield f"data: {json.dumps({'done': True, 'message_id': assistant_msg.id, 'title': chat.title})}\n\n"

    return StreamingResponse(response_stream(), media_type="text/event-stream")

@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id).first()
    if not chat: raise HTTPException(status_code=404, detail="Chat not found")
    cleanup_chat_assets(chat_id, current_user.id, db)
    db.delete(chat)
    db.commit()
    return {"message": "Policy chat deleted"}
