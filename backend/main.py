import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from config import UPLOAD_DIR
from routers import auth, general_chat, document_chat, spreadsheet_chat, policy_chat

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(title="Defense Chat System")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(auth.router)
app.include_router(general_chat.router)
app.include_router(document_chat.router)
app.include_router(spreadsheet_chat.router)
app.include_router(policy_chat.router)


@app.on_event("startup")
async def startup():
    # Import all models to ensure they're registered
    import models  # noqa
    Base.metadata.create_all(bind=engine)
    logger.info("Defense Chat System started successfully")


@app.get("/api/health")
def health_check():
    return {"status": "operational", "system": "Defense Chat System"}
