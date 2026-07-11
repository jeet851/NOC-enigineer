from pydantic import BaseModel

class ActionRequest(BaseModel):
    scenario: str
    action: str

class ActionResponse(BaseModel):
    output: str
