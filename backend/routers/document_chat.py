import os
import json
import re
import logging
import decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from models.user import User
from models.chat import Chat, ChatMessage
from models.document import DocumentUpload, FAISSMapping, TableMapping
from middleware.auth_middleware import get_current_user
from services.document_service import convert_to_pdf, extract_content
from services.chunking_service import chunk_text
from services.vector_service import create_faiss_index, search_faiss_index, delete_faiss_index
from services.table_service import (
    preprocess_and_store_table, get_table_schema,
    generate_sql, execute_sql, drop_tables
)
from services.ollama_service import generate_response_stream, generate_response_sync, generate_chat_title
from services.cleanup_service import cleanup_chat_assets
from config import DOCUMENTS_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat/document", tags=["document-chat"])


class SendMessageRequest(BaseModel):
    content: str
    upload_timestamp: Optional[str] = None
    table_mode: bool = False


class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Document Chat"


class RenameChatRequest(BaseModel):
    title: str


@router.post("")
def create_chat(
    req: CreateChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat = Chat(user_id=current_user.id, title=req.title, chat_type="document")
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
        Chat.chat_type == "document"
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

    # Get uploads for this chat
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
async def upload_documents(
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
    all_tables = []
    processed_files = []

    for file in files:
        # Save uploaded file
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Convert to PDF
        try:
            pdf_path = convert_to_pdf(file_path)
        except Exception as e:
            logger.error(f"Conversion error for {file.filename}: {e}")
            pdf_path = file_path  # Try to process original if conversion fails

        # Extract content
        try:
            extracted = extract_content(pdf_path)
            all_text += f"\n\n--- {file.filename} ---\n\n" + extracted["text_content"]
            all_tables.extend(extracted["tables"])
        except Exception as e:
            logger.error(f"Extraction error for {file.filename}: {e}")
            # Try basic text read as fallback
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    all_text += f"\n\n--- {file.filename} ---\n\n" + f.read()
            except Exception:
                pass

        # Record upload
        doc_upload = DocumentUpload(
            chat_id=chat_id, user_id=current_user.id,
            filename=file.filename, upload_timestamp=upload_timestamp,
            pdf_path=pdf_path
        )
        db.add(doc_upload)
        processed_files.append(file.filename)

    # Process text chunks and create FAISS index
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

    # Process tables
    table_names = []
    for i, df in enumerate(all_tables):
        table_name = f"doc_t{chat_id}_u{current_user.id}_{upload_timestamp}_tbl{i}"
        table_name = re.sub(r'[^a-z0-9_]', '', table_name.lower())
        try:
            preprocess_and_store_table(df, table_name, db)
            table_mapping = TableMapping(
                chat_id=chat_id, user_id=current_user.id,
                upload_timestamp=upload_timestamp, table_name=table_name
            )
            db.add(table_mapping)
            table_names.append(table_name)
        except Exception as e:
            logger.error(f"Table storage error: {e}")

    db.commit()

    # Auto-generate title if first upload
    upload_count = db.query(DocumentUpload).filter(DocumentUpload.chat_id == chat_id).count()
    if upload_count == len(files):
        filenames = ", ".join(processed_files)
        try:
            new_title = await generate_chat_title(f"Document analysis: {filenames}")
            chat.title = new_title
            db.commit()
        except Exception:
            chat.title = f"Docs: {filenames[:50]}"
            db.commit()

    # Add system message about upload
    sys_content = f"📄 Uploaded {len(processed_files)} document(s): {', '.join(processed_files)}."
    if faiss_created:
        sys_content += f" Text extracted and indexed for semantic search."
    if table_names:
        sys_content += f" {len(table_names)} table(s) extracted and stored for SQL queries."

    sys_msg = ChatMessage(chat_id=chat_id, role="assistant", content=sys_content)
    db.add(sys_msg)
    db.commit()

    return {
        "message": "Documents processed successfully",
        "upload_timestamp": upload_timestamp,
        "files_processed": processed_files,
        "text_indexed": faiss_created,
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

    # Save user message
    user_msg = ChatMessage(chat_id=chat_id, role="user", content=req.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Get the latest upload timestamp for this chat (per-upload isolation)
    latest_upload = db.query(DocumentUpload).filter(
        DocumentUpload.chat_id == chat_id,
        DocumentUpload.user_id == current_user.id
    ).order_by(DocumentUpload.upload_timestamp.desc()).first()

    if not latest_upload:
        # No documents uploaded yet, respond normally
        async def no_doc_stream():
            yield f"data: {json.dumps({'content': 'Please upload documents first before asking questions.'})}\n\n"
            msg = ChatMessage(chat_id=chat_id, role="assistant",
                              content="Please upload documents first before asking questions.")
            db.add(msg)
            db.commit()
            yield f"data: {json.dumps({'done': True, 'message_id': msg.id})}\n\n"
        return StreamingResponse(no_doc_stream(), media_type="text/event-stream")

    # Use the specific upload_timestamp if provided, else use latest
    active_timestamp = req.upload_timestamp or latest_upload.upload_timestamp


    # Step 2: Retrieve Context (Hybrid Approach)
    faiss_context = ""
    sql_results = None

    # Always try to get semantic context if available
    faiss_mapping = db.query(FAISSMapping).filter(
        FAISSMapping.chat_id == chat_id,
        FAISSMapping.user_id == current_user.id,
        FAISSMapping.upload_timestamp == active_timestamp
    ).first()
    
    if faiss_mapping:
        results = search_faiss_index(
            req.content, faiss_mapping.faiss_index_path,
            faiss_mapping.chunks_path, top_k=5
        )
        if results:
            faiss_context = "\n\n".join([r["chunk"]["text"] for r in results])

    # Check for tables
    table_mappings = db.query(TableMapping).filter(
        TableMapping.chat_id == chat_id,
        TableMapping.user_id == current_user.id,
        TableMapping.upload_timestamp == active_timestamp
    ).all()

    # Step 3: Determine if SQL is needed based on query and retrieved semantic context
    # If the query is numeric or precise, intent will favor SQL
    if req.table_mode and table_mappings:
        logger.info(f"Table Mode activated by user flag for chat {chat_id}")
        intent = "sql"
        # In explicit table mode, we ignore semantic search context to prevent LLM confusion
        faiss_context = ""
    else:
        intent = await _determine_intent(req.content, faiss_context, bool(table_mappings))
        logger.info(f"Determined intent as: {intent} for chat {chat_id}")

    # SQL Execution if intent suggests it
    if intent == "sql" and table_mappings:
        schemas = [get_table_schema(tm.table_name, db) for tm in table_mappings]
        schemas = [s for s in schemas if s["columns"]]
        if schemas:
            try:
                sql = await generate_sql(schemas, req.content)
                sql_results = execute_sql(sql, db)
            except Exception as e:
                logger.error(f"SQL generation/execution error: {e}")
                sql_results = {"error": str(e), "data": []}


    # Step 4: Generate response with context
    async def response_stream():
        messages_for_llm = _build_llm_messages(
            chat, faiss_context, sql_results, req.content, db
        )

        full_response = ""
        async for chunk in generate_response_stream(messages_for_llm):
            full_response += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"

        # Append SQL results and chart info if available
        if sql_results and sql_results.get("data") and not sql_results.get("error"):
            table_info = json.dumps({
                "type": "table",
                "columns": sql_results["columns"],
                "data": sql_results["data"][:50],
                "sql": sql_results.get("sql", ""),
                "row_count": sql_results["row_count"]
            })
            full_response += f"\n\n<!--TABLE_DATA:{table_info}-->"
            yield f"data: {json.dumps({'table_data': sql_results})}\n\n"


        # Save assistant message
        assistant_msg = ChatMessage(
            chat_id=chat_id, role="assistant",
            content=full_response
        )
        db.add(assistant_msg)
        db.commit()

        yield f"data: {json.dumps({'done': True, 'message_id': assistant_msg.id, 'title': chat.title})}\n\n"

    return StreamingResponse(response_stream(), media_type="text/event-stream")


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

    # Clean up FAISS indexes, documents, and tables
    cleanup_chat_assets(chat_id, current_user.id, db)


    # Delete chat (cascades to messages, uploads, mappings)
    db.delete(chat)
    db.commit()

    return {"message": "Chat and all associated data deleted"}


# --- Helper functions ---

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


async def _determine_intent(query: str, context: str, has_tables: bool) -> str:
    """Use LLM to determine user intent: search, sql, chart, or general."""
    if not has_tables:
        return "search"

    messages = [
        {
            "role": "system",
            "content": """Analyze the user query and the provided document snippets to determine if a database (SQL) query is needed for an accurate answer.
            
SQL is needed if:
- The user asks for specific numbers, sums, averages, or counts.
- The user asks for a chart or visualization.
- The user asks for filtered lists or details that are structured in tables.

Semantic search (FAISS) is used for:
- General "what", "why", "how" questions based on text.
- Summaries of descriptive content.

Output ONLY one of these strings: "search", "sql"."""
        },
        {
            "role": "user",
            "content": f"Query: {query}\n\nDocument Snippets:\n{context[:2000]}"
        }
    ]

    try:
        response = await generate_response_sync(messages)
        intent = response.strip().lower()
        if "sql" in intent or "chart" in intent: return "sql"
        return "search"
    except Exception:
        return "search"




def _build_llm_messages(chat: Chat, context: str, sql_results: dict,
                        user_query: str, db: Session) -> list:
    """Build message history for LLM with context."""
    system_prompt = """You are a highly capable AI assistant for defense personnel, operating in a secure airgapped environment.
You help users analyze uploaded documents by answering questions based on the extracted content.

CAPABILITIES:
- Answer questions using document text content retrieved via semantic search
- Analyze tabular data from documents using SQL query results

RULES:
- Base your answers ONLY on the provided context and data
- If SQL results are provided, summarize them clearly in your response
- If the context doesn't contain relevant information, say so clearly
- Be concise, accurate, and professional
- Format numbers and tables neatly in your response"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add previous messages (last 10 for context window management)
    prev_messages = db.query(ChatMessage).filter(
        ChatMessage.chat_id == chat.id
    ).order_by(ChatMessage.created_at.desc()).limit(10).all()

    for msg in reversed(prev_messages[:-1]):  # Exclude the just-added user message
        clean_content = msg.content
        # Remove embedded data markers
        clean_content = re.sub(r'<!--TABLE_DATA:.*?-->', '', clean_content, flags=re.DOTALL)
        if clean_content.strip():
            messages.append({"role": msg.role, "content": clean_content.strip()})

    # Add context
    user_content = user_query
    if context:
        user_content = f"DOCUMENT CONTEXT:\n{context}\n\nUSER QUESTION: {user_query}"
    if sql_results and sql_results.get("data") and not sql_results.get("error"):
        sql_info = f"\n\nSQL QUERY RESULTS (SQL: {sql_results.get('sql', '')}):\n"
        sql_info += f"Columns: {sql_results.get('columns', [])}\n"
        data_preview = sql_results["data"][:20]
        sql_info += f"Data ({sql_results.get('row_count', 0)} rows total):\n{json.dumps(data_preview, indent=2, default=json_serial)}"
        user_content += sql_info
    elif sql_results and sql_results.get("error"):
        user_content += f"\n\nNote: SQL query failed with error: {sql_results['error']}"


    messages.append({"role": "user", "content": user_content})
    return messages
