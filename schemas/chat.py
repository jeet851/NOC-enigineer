from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    sessionId: str = "default_session"
    persona: str = "assistant"
    scenario: str = ""
    uploadedLogs: Optional[str] = None
    uploadedConfig: Optional[str] = None
    uploadedTopology: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    persona: str
    routed: bool
    isScenario: bool
    scenarioKey: Optional[str] = None

class ClearChatRequest(BaseModel):
    sessionId: str
