from pydantic import BaseModel
from typing import List, Optional

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    title: str
    description: Optional[str] = None
    semester: int
    subject: str

class DocumentCreate(DocumentBase):
    pass

class Document(DocumentBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    question: str
    user_id: int
    semester: Optional[int] = None
    subject: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[str]

class ModelConfig(BaseModel):
    model_name: str
    embedding_model: str
    temperature: float = 0.7