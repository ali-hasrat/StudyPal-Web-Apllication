import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List

from . import schemas, models
from .database import engine
from .rag import RAGSystem
from .models import User, Document
from .schemas import UserCreate, User, DocumentCreate, Document, ChatRequest, ChatResponse, ModelConfig
from .database import SessionLocal, engine
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from .config import settings
import shutil

# Create database tables
models.Base.metadata.create_all(bind=engine)

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT configuration
SECRET_KEY = "your-secret-key"  # In production, use a proper secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Initialize RAG system
rag_system = RAGSystem()


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Helper functions for authentication
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# Auth endpoints
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    try:
        print("Received registration for:", user.username)  # Debug log
        db_user = db.query(models.User).filter(models.User.username == user.username).first()
        if db_user:
            print("Username exists")  # Debug log
            raise HTTPException(status_code=400, detail="Username already registered")

        hashed_password = get_password_hash(user.password)
        print("Password hashed")  # Debug log

        db_user = models.User(
            username=user.username,
            email=user.email,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        print("User created:", db_user.id)  # Debug log
        return db_user

    except Exception as e:
        print("Registration failed:", str(e))  # Critical debug log
        raise HTTPException(status_code=500, detail=str(e))
# Document endpoints
@app.post("/documents/upload/")
async def upload_document(
        file: UploadFile = File(...),
        semester: int = 1,
        subject: str = "General",
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Save file temporarily
    file_location = f"uploads/{current_user.id}_{file.filename}"
    os.makedirs("uploads", exist_ok=True)

    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    # Ingest document into RAG system
    metadata = {
        "user_id": current_user.id,
        "semester": semester,
        "subject": subject,
        "title": file.filename
    }

    success = rag_system.ingest_document(file_location, metadata)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to process document")

    # Save document metadata to SQL database
    db_document = Document(
        title=file.filename,
        semester=semester,
        subject=subject,
        file_path=file_location,
        owner_id=current_user.id
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    return {"filename": file.filename, "success": True}


@app.get("/documents/", response_model=List[Document])
def get_user_documents(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    documents = db.query(Document).filter(Document.owner_id == current_user.id).all()
    return documents


# Chat endpoints
@app.post("/chat/", response_model=ChatResponse)
async def chat_with_documents(
        chat_request: ChatRequest,
        current_user: User = Depends(get_current_user)
):
    response = rag_system.query(
        question=chat_request.question,
        user_id=current_user.id,
        semester=chat_request.semester,
        subject=chat_request.subject
    )
    return ChatResponse(answer=response["answer"], sources=response["sources"])


# Admin endpoints
@app.post("/admin/update_model/")
async def update_model_config(
        config: ModelConfig,
        current_user: User = Depends(get_current_user)
):
    # In a real app, verify user is admin
    settings.model_name = config.model_name
    settings.embedding_model = config.embedding_model
    return {"message": "Model configuration updated successfully"}


@app.get("/")
def read_root():
    return {"message": "Welcome to StudyPal API"}