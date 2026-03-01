-- =============================================================
-- Defense Chat System - PostgreSQL Setup Script
-- Run this script to create the database and initial schema
-- Usage: psql -U postgres -f setup.sql
-- =============================================================

-- Create database
CREATE DATABASE defense_chat;

-- Connect to the database
\c defense_chat;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chats table
CREATE TABLE IF NOT EXISTS chats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) DEFAULT 'New Chat',
    chat_type VARCHAR(20) NOT NULL CHECK (chat_type IN ('general', 'document')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document uploads table
CREATE TABLE IF NOT EXISTS document_uploads (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    upload_timestamp VARCHAR(50) NOT NULL,
    pdf_path VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- FAISS index mappings
CREATE TABLE IF NOT EXISTS faiss_mappings (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    upload_timestamp VARCHAR(50) NOT NULL,
    faiss_index_path VARCHAR(500) NOT NULL,
    chunks_path VARCHAR(500) NOT NULL
);

-- Table mappings (for dynamically created tables from document tables)
CREATE TABLE IF NOT EXISTS table_mappings (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    upload_timestamp VARCHAR(50) NOT NULL,
    table_name VARCHAR(255) NOT NULL
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_type ON chats(chat_type);
CREATE INDEX IF NOT EXISTS idx_chats_title ON chats(title);
CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_document_uploads_chat_id ON document_uploads(chat_id);
CREATE INDEX IF NOT EXISTS idx_document_uploads_timestamp ON document_uploads(upload_timestamp);
CREATE INDEX IF NOT EXISTS idx_faiss_mappings_lookup ON faiss_mappings(chat_id, user_id, upload_timestamp);
CREATE INDEX IF NOT EXISTS idx_table_mappings_lookup ON table_mappings(chat_id, user_id, upload_timestamp);

-- Grant permissions (adjust user as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;

RAISE NOTICE 'Defense Chat System database setup complete!';
