import os
import json
import re
import logging
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from models.user import User
from models.chat import Chat, ChatMessage
from models.document import DocumentUpload, TableMapping
from middleware.auth_middleware import get_current_user
from services.table_service import (
    preprocess_and_store_table, get_table_schema,
    generate_sql, execute_sql
)
from services.ollama_service import generate_response_stream, generate_chat_title
from services.cleanup_service import cleanup_chat_assets
from config import DOCUMENTS_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/spreadsheet", tags=["spreadsheet-chat"])

class SendMessageRequest(BaseModel):
    content: str
    upload_timestamp: Optional[str] = None

class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Spreadsheet Chat"

@router.post("")
def create_chat(
    req: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = Chat(user_id=current_user.id, title=req.title, chat_type="spreadsheet")
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
        Chat.chat_type == "spreadsheet"
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
async def upload_spreadsheet(
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

    processed_files = []
    table_names = []

    for file in files:
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
            continue

        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path, engine='openpyxl')
            
            if not df.empty:
                table_name = f"sheet_t{chat_id}_u{current_user.id}_{upload_timestamp}_{len(table_names)}"
                table_name = re.sub(r'[^a-z0-9_]', '', table_name.lower())
                
                # Unified numeric detection and cleaning
                preprocess_and_store_table(df, table_name, db, is_spreadsheet=True)
                
                table_mapping = TableMapping(
                    chat_id=chat_id, user_id=current_user.id,
                    upload_timestamp=upload_timestamp, table_name=table_name
                )
                db.add(table_mapping)
                table_names.append(table_name)
                processed_files.append(file.filename)
                
                # Record upload
                doc_upload = DocumentUpload(
                    chat_id=chat_id, user_id=current_user.id,
                    filename=file.filename, upload_timestamp=upload_timestamp
                )
                db.add(doc_upload)
        except Exception as e:
            logger.error(f"Spreadsheet processing error for {file.filename}: {e}")

    db.commit()

    if processed_files:
        # Update title if first upload
        upload_count = db.query(DocumentUpload).filter(DocumentUpload.chat_id == chat_id).count()
        if upload_count == len(processed_files):
            try:
                chat.title = await generate_chat_title(f"Spreadsheet analysis: {processed_files[0]}")
                db.commit()
            except Exception: pass

        sys_content = f"📊 Uploaded {len(processed_files)} spreadsheet(s): {', '.join(processed_files)}."
        sys_content += f" {len(table_names)} table(s) stored for SQL analysis."
        sys_msg = ChatMessage(chat_id=chat_id, role="assistant", content=sys_content)
        db.add(sys_msg)
        db.commit()

    return {
        "message": "Spreadsheets processed successfully",
        "upload_timestamp": upload_timestamp,
        "files_processed": processed_files,
        "tables_stored": len(table_names),
        "chat_title": chat.title
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

    user_msg = ChatMessage(chat_id=chat_id, role="user", content=req.content)
    db.add(user_msg)
    db.commit()

    latest_upload = db.query(DocumentUpload).filter(
        DocumentUpload.chat_id == chat_id,
        DocumentUpload.user_id == current_user.id
    ).order_by(DocumentUpload.upload_timestamp.desc()).first()

    if not latest_upload:
        async def no_doc_stream():
            yield f"data: {json.dumps({'content': 'Please upload spreadsheets first.'})}\n\n"
            msg = ChatMessage(chat_id=chat_id, role="assistant", content="Please upload spreadsheets first.")
            db.add(msg)
            db.commit()
            yield f"data: {json.dumps({'done': True, 'message_id': msg.id})}\n\n"
        return StreamingResponse(no_doc_stream(), media_type="text/event-stream")

    active_timestamp = req.upload_timestamp or latest_upload.upload_timestamp
    table_mappings = db.query(TableMapping).filter(
        TableMapping.chat_id == chat_id,
        TableMapping.upload_timestamp == active_timestamp
    ).all()

    sql_results = None
    if table_mappings:
        schemas = [get_table_schema(tm.table_name, db) for tm in table_mappings]
        schemas = [s for s in schemas if s["columns"]]
        if schemas:
            try:
                sql = await generate_sql(schemas, req.content)
                sql_results = execute_sql(sql, db)
            except Exception as e:
                logger.error(f"SQL generation/execution error: {e}")
                sql_results = {"error": str(e), "data": []}

    async def response_stream():
        from routers.document_chat import _build_llm_messages
        messages_for_llm = _build_llm_messages(chat, "", sql_results, req.content, db)
        
        full_response = ""
        async for chunk in generate_response_stream(messages_for_llm):
            full_response += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"

        if sql_results and sql_results.get("data") and not sql_results.get("error"):
            import decimal
            def json_serial(obj):
                if isinstance(obj, decimal.Decimal): return float(obj)
                raise TypeError(f"Type {type(obj)} not serializable")
            
            table_info = json.dumps({
                "type": "table", "columns": sql_results["columns"],
                "data": sql_results["data"][:50], "sql": sql_results.get("sql", ""),
                "row_count": sql_results["row_count"]
            }, default=json_serial)
            full_response += f"\n\n<!--TABLE_DATA:{table_info}-->"
            yield f"data: {json.dumps({'table_data': sql_results})}\n\n"

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
    return {"message": "Spreadsheet chat deleted"}
