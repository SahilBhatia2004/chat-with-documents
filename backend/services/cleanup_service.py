import os
import shutil
import logging
from sqlalchemy.orm import Session
from config import DOCUMENTS_DIR, FAISS_DIR
from models.document import TableMapping, DocumentUpload, FAISSMapping
from services.table_service import drop_tables

logger = logging.getLogger(__name__)

def cleanup_chat_assets(chat_id: int, user_id: int, db: Session):
    """Delete all local files, FAISS indexes, and database tables for a chat."""
    
    # 1. Clean up FAISS indexes directories
    # The structure is FAISS_DIR/chat_{chat_id}/user_{user_id}
    chat_faiss_dir = os.path.join(FAISS_DIR, f"chat_{chat_id}")
    if os.path.exists(chat_faiss_dir):
        try:
            shutil.rmtree(chat_faiss_dir)
            logger.info(f"Deleted FAISS chat directory: {chat_faiss_dir}")
        except Exception as e:
            logger.error(f"Error deleting FAISS directory {chat_faiss_dir}: {e}")

    # 2. Clean up document uploads directories
    # The structure is DOCUMENTS_DIR/{chat_id}
    chat_doc_dir = os.path.join(DOCUMENTS_DIR, str(chat_id))
    if os.path.exists(chat_doc_dir):
        try:
            shutil.rmtree(chat_doc_dir)
            logger.info(f"Deleted documents chat directory: {chat_doc_dir}")
        except Exception as e:
            logger.error(f"Error deleting documents directory {chat_doc_dir}: {e}")

    # 3. Clean up dynamic tables
    try:
        table_mappings = db.query(TableMapping).filter(TableMapping.chat_id == chat_id).all()
        table_names = [tm.table_name for tm in table_mappings]
        if table_names:
            drop_tables(table_names, db)
    except Exception as e:
        logger.error(f"Error dropping tables for chat {chat_id}: {e}")

def cleanup_document_assets(document_id: int, db: Session):
    """Delete assets for a single document upload (used in Policy Chat)."""
    doc = db.query(DocumentUpload).filter(DocumentUpload.id == document_id).first()
    if not doc:
        return
    
    chat_id = doc.chat_id
    user_id = doc.user_id
    upload_timestamp = doc.upload_timestamp
    
    # Process FAISS index cleanup for this specific timestamp
    faiss_mappings = db.query(FAISSMapping).filter(
        FAISSMapping.chat_id == chat_id,
        FAISSMapping.upload_timestamp == upload_timestamp
    ).all()
    
    for fm in faiss_mappings:
        # FAISS_DIR/chat_{chat_id}/user_{user_id}/{timestamp}
        index_dir = os.path.dirname(fm.faiss_index_path)
        if os.path.exists(index_dir):
            try:
                shutil.rmtree(index_dir)
                logger.info(f"Deleted FAISS index directory: {index_dir}")
            except Exception as e:
                logger.error(f"Error deleting FAISS directory {index_dir}: {e}")
        db.delete(fm)
        
    # Process Table cleanup for this specific timestamp
    table_mappings = db.query(TableMapping).filter(
        TableMapping.chat_id == chat_id,
        TableMapping.upload_timestamp == upload_timestamp
    ).all()
    
    table_names = [tm.table_name for tm in table_mappings]
    if table_names:
        drop_tables(table_names, db)
    
    for tm in table_mappings:
        db.delete(tm)
        
    # Delete local files
    # DOCUMENTS_DIR/{chat_id}/{timestamp}
    doc_dir = os.path.join(DOCUMENTS_DIR, str(chat_id), upload_timestamp)
    if os.path.exists(doc_dir):
        try:
            shutil.rmtree(doc_dir)
            logger.info(f"Deleted document directory: {doc_dir}")
        except Exception as e:
            logger.error(f"Error deleting document directory {doc_dir}: {e}")
            
    # Delete document record
    db.delete(doc)
    db.commit()
    logger.info(f"Document {document_id} and associated assets deleted.")
