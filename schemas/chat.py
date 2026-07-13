from pydantic import BaseModel
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    message: str
    sessionId: str = "default_session"
    persona: str = "assistant"
    scenario: str = ""
    uploadedLogs: Optional[str] = None
    uploadedConfig: Optional[str] = None
    uploadedTopology: Optional[str] = None
    userRole: Optional[str] = None   # Phase 3: operator role for context-aware routing

class ChatResponse(BaseModel):
    response: str
    persona: str
    routed: bool
    isScenario: bool
    scenarioKey: Optional[str] = None
    explainability: Optional[Dict[str, Any]] = None  # Phase 3: structured reasoning metadata

class ClearChatRequest(BaseModel):
    sessionId: str
