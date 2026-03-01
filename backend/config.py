import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/defense_chat")

# JWT
JWT_SECRET = os.getenv("JWT_SECRET", "defense-chat-secret-key-change-in-production-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DOCUMENTS_DIR = os.path.join(UPLOAD_DIR, "documents")
FAISS_DIR = os.path.join(UPLOAD_DIR, "faiss_indexes")

# Ensure directories exist
for d in [UPLOAD_DIR, DOCUMENTS_DIR, FAISS_DIR]:
    os.makedirs(d, exist_ok=True)

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# LibreOffice
LIBREOFFICE_PATH = os.getenv(
    "LIBREOFFICE_PATH",
    r"C:\Program Files\LibreOffice\program\soffice.exe"
)
