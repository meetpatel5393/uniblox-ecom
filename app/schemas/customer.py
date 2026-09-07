import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    created_at: datetime
