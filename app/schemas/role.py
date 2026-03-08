from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class RoleBase(BaseModel):
    name: str
    permissions: Optional[str] = None

class RoleCreate(RoleBase):
    pass

class RoleUpdate(RoleBase):
    name: Optional[str] = None

class RoleInDBBase(RoleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Role(RoleInDBBase):
    pass
