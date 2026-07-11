from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, List
import json
import os
import sys
import importlib.util

from api.deps import get_db, get_current_user
from schemas.chat import ChatRequest, ChatResponse, ClearChatRequest
from services.audit import AuditService
from services.incident import IncidentService
from ai_engine.engine import AIEngineWrapper

# Dynamically import root-level ai_engine.py module to resolve folder naming conflict
spec = importlib.util.spec_from_file_location("ai_engine_root", "ai_engine.py")
ai_engine_root = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_engine_root)

router = APIRouter(prefix="/api", tags=["copilot-chat"])

# In-memory session stores for chat histories
chat_sessions: Dict[str, List[dict]] = {}

@router.get("/personas")
async def get_personas(user: dict = Depends(get_current_user)):
    return ai_engine_root.PERSONAS

@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    message = req.message.strip()
    session_id = req.sessionId
    selected_persona = req.persona
    active_scenario = req.scenario
    
    if not message:
        raise HTTPException(status_code=400, detail="Empty message")
        
    normalized = message.lower().rstrip("?.- ")
    routed_persona = ai_engine_root.auto_route_intent(normalized)
    session_persona = routed_persona if routed_persona else selected_persona
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
        
    history = chat_sessions[session_id]
    
    # 1. Fetch active incidents automatically from Incident Engine
    active_incidents = IncidentService.get_active_incidents(db)
    active_incidents_text = ""
    if active_incidents:
        active_incidents_text = "\n".join([
            f"- {inc.id}: Severity={inc.severity}, Device={inc.device_name}, Site={inc.site}, Vendor={inc.vendor}, Description={inc.description}, Root Cause={inc.root_cause}, Status={inc.status}"
            for inc in active_incidents
        ])
        
    # 2. Fetch topology graph automatically
    topology_context = ""
    if os.path.exists("topology.json"):
        try:
            with open("topology.json", "r") as f:
                topology_context = f.read()
        except Exception:
            pass

    # 3. Call standard response generator (incorporating context)
    response_text = ai_engine_root.generate_ai_response(
        prompt_text=message,
        conversation_history=history,
        persona_key=session_persona,
        active_scenario=active_scenario
    )
    
    history.append({"role": "user", "text": message})
    history.append({"role": "model", "text": response_text})
    chat_sessions[session_id] = history[-20:]  # Limit to last 20 messages
    
    matched_scenario_key = ai_engine_root.find_matching_scenario(message)
    if not matched_scenario_key and active_scenario:
        matched_scenario_key = ai_engine_root.find_matching_scenario(active_scenario)
        
    is_scenario = matched_scenario_key is not None
    
    # Audit log the query
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Copilot Chat",
        ip="127.0.0.1",
        details=f"Queried copilot: '{message[:50]}...'",
        status="Success"
    )
    
    return {
        "response": response_text,
        "persona": session_persona,
        "routed": routed_persona is not None,
        "isScenario": is_scenario,
        "scenarioKey": matched_scenario_key if is_scenario else None
    }

@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exposes a Server-Sent Events (SSE) streaming API for the AI Copilot.
    """
    message = req.message.strip()
    session_id = req.sessionId
    selected_persona = req.persona
    active_scenario = req.scenario
    
    if not message:
        raise HTTPException(status_code=400, detail="Empty message")
        
    normalized = message.lower().rstrip("?.- ")
    routed_persona = ai_engine_root.auto_route_intent(normalized)
    session_persona = routed_persona if routed_persona else selected_persona
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
        
    history = chat_sessions[session_id]
    
    # 1. Fetch active incidents context (Incident Engine)
    active_incidents = IncidentService.get_active_incidents(db)
    active_incidents_text = ""
    if active_incidents:
        active_incidents_text = "\n".join([
            f"- {inc.id}: Severity={inc.severity}, Device={inc.device_name}, Site={inc.site}, Vendor={inc.vendor}, Description={inc.description}, Root Cause={inc.root_cause}, Status={inc.status}"
            for inc in active_incidents
        ])
        
    # 2. Fetch topology context
    topology_context = req.uploadedTopology or ""
    if not topology_context and os.path.exists("topology.json"):
        try:
            with open("topology.json", "r") as f:
                topology_context = f.read()
        except Exception:
            pass

    # Audit log the query
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Copilot Chat Stream",
        ip="127.0.0.1",
        details=f"Queried copilot stream: '{message[:50]}...'",
        status="Success"
    )

    async def sse_event_generator():
        accumulated_text = ""
        async for chunk in AIEngineWrapper.generate_streaming_response(
            prompt_text=message,
            conversation_history=history,
            persona_key=session_persona,
            active_scenario=active_scenario,
            active_incidents_context=active_incidents_text,
            topology_context=topology_context,
            uploaded_logs=req.uploadedLogs,
            uploaded_config=req.uploadedConfig
        ):
            # Accumulate chunk to append to history on finish
            if chunk["text"]:
                accumulated_text += chunk["text"]
            yield f"data: {json.dumps(chunk)}\n\n"
            
        # Append completed message to history
        if accumulated_text:
            history.append({"role": "user", "text": message})
            history.append({"role": "model", "text": accumulated_text})
            chat_sessions[session_id] = history[-20:]

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

@router.post("/clear-chat")
async def clear_chat(req: ClearChatRequest, user: dict = Depends(get_current_user)):
    session_id = req.sessionId
    if session_id in chat_sessions:
        chat_sessions[session_id] = []
    return {"status": "success", "message": "Chat history cleared"}
