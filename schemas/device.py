from pydantic import BaseModel
from typing import Optional

class DeviceSchema(BaseModel):
    name: str
    ip: str
    vendor: str
    platform: str
    status: str
    role: str
    site: str
    description: Optional[str] = None

    class Config:
        from_attributes = True
