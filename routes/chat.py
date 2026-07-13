import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
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

# Phase 3 imports
from ai_engine.memory_manager import MemoryManager
from ai_engine.context_engine import ContextEngine
from ai_engine.explainability import ExplainabilityEngine
from ai_engine.recommendations_engine import RecommendationsEngine

router = APIRouter(prefix="/api", tags=["copilot-chat"])
logger = logging.getLogger("noc.chat")


@router.get("/personas")
async def get_personas(user: dict = Depends(get_current_user)):
    return ai_engine_root.PERSONAS


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    message = req.message.strip()
    session_id = req.sessionId
    selected_persona = req.persona
    active_scenario = req.scenario
    user_role = req.userRole or user.get("role", "viewer")

    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    # ── Phase 3: Build full operational context ──────────────────────
    ctx = ContextEngine.build_context(
        db=db,
        user={"username": user.get("username", "unknown"), "role": user_role},
        conversation_history=MemoryManager.get_history(session_id, db=db),
        active_scenario=active_scenario,
    )

    # ── Phase 3: Enhanced intent routing with context signals ─────────
    routed_persona = ai_engine_root.auto_route_intent(
        message,
        conversation_history=MemoryManager.get_history(session_id, db=db),
        active_incidents=ctx.get("active_incidents"),
        user_role=user_role,
    )
    session_persona = routed_persona if routed_persona else selected_persona

    # ── Phase 3: Load history from persistent memory ──────────────────
    history = MemoryManager.get_history(session_id, db=db)

    # ── Phase 3: Inject memory context for follow-up questions ───────
    memory_context = MemoryManager.build_memory_context(session_id, message, db=db)
    memory_context_used = bool(memory_context)

    # Build incidents/topology context strings
    active_incidents_text = ""
    if ctx.get("active_incidents"):
        active_incidents_text = "\n".join([
            f"- {inc['id']}: Severity={inc['severity']}, Device={inc['device_name']}, "
            f"Site={inc.get('site','?')}, Vendor={inc.get('vendor','?')}, "
            f"Description={inc['description']}, Root Cause={inc['root_cause']}, Status={inc['status']}"
            for inc in ctx["active_incidents"]
        ])

    topology_context = json.dumps(ctx.get("topology", {})) if ctx.get("topology") else ""

    # Prepend operational context to system prompt via extra context injection
    structured_context_str = ContextEngine.format_for_prompt(ctx)
    if memory_context:
        structured_context_str = memory_context + "\n\n" + structured_context_str

    # Call standard response generator
    response_text = ai_engine_root.generate_ai_response(
        prompt_text=message,
        conversation_history=history,
        persona_key=session_persona,
        active_scenario=active_scenario
    )

    # ── Phase 3: Persist to memory ───────────────────────────────────
    MemoryManager.append_message(session_id, "user", message, persona=session_persona, db=db)
    MemoryManager.append_message(session_id, "model", response_text, persona=session_persona, db=db)

    matched_scenario_key = ai_engine_root.find_matching_scenario(message)
    if not matched_scenario_key and active_scenario:
        matched_scenario_key = ai_engine_root.find_matching_scenario(active_scenario)

    is_scenario = matched_scenario_key is not None

    # ── Phase 3: Build explainability metadata ────────────────────────
    routing_score = 5 if routed_persona else 0
    exp = ExplainabilityEngine.build(
        prompt=message,
        persona_selected=session_persona,
        persona_reason=f"Auto-routed to {session_persona}" if routed_persona else f"User selected {session_persona}",
        routing_score=routing_score,
        context=ctx,
        scenario_key=matched_scenario_key,
        memory_context_used=memory_context_used,
        response_text=response_text,
    )

    # Store explainability record
    ExplainabilityEngine.store(exp, message, response_text, db=db)

    # Audit log
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Copilot Chat",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Queried copilot: '{message[:50]}...'",
        status="Success"
    )

    return {
        "response": response_text,
        "persona": session_persona,
        "routed": routed_persona is not None,
        "isScenario": is_scenario,
        "scenarioKey": matched_scenario_key if is_scenario else None,
        "explainability": exp,
    }


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exposes a Server-Sent Events (SSE) streaming API for the AI Copilot.
    Phase 3: Persistent memory, structured context, and explainability metadata
    are included in the final SSE chunk.
    """
    message = req.message.strip()
    session_id = req.sessionId
    selected_persona = req.persona
    active_scenario = req.scenario
    user_role = req.userRole or user.get("role", "viewer")

    if not message:
        raise HTTPException(status_code=400, detail="Empty message")

    # ── Phase 3: Build full operational context ──────────────────────
    ctx = ContextEngine.build_context(
        db=db,
        user={"username": user.get("username", "unknown"), "role": user_role},
        conversation_history=MemoryManager.get_history(session_id, db=db),
        active_scenario=active_scenario,
    )

    # ── Phase 3: Enhanced intent routing ─────────────────────────────
    routed_persona = ai_engine_root.auto_route_intent(
        message,
        conversation_history=MemoryManager.get_history(session_id, db=db),
        active_incidents=ctx.get("active_incidents"),
        user_role=user_role,
    )
    session_persona = routed_persona if routed_persona else selected_persona

    # ── Phase 3: Load persistent history ─────────────────────────────
    history = MemoryManager.get_history(session_id, db=db)

    # ── Phase 3: Memory context for follow-up questions ──────────────
    memory_context = MemoryManager.build_memory_context(session_id, message, db=db)
    memory_context_used = bool(memory_context)

    # Build context strings
    active_incidents_text = ""
    if ctx.get("active_incidents"):
        active_incidents_text = "\n".join([
            f"- {inc['id']}: Severity={inc['severity']}, Device={inc['device_name']}, "
            f"Description={inc['description']}, Root Cause={inc['root_cause']}, Status={inc['status']}"
            for inc in ctx["active_incidents"]
        ])

    topology_context = req.uploadedTopology or ""
    if not topology_context and ctx.get("topology"):
        topology_context = json.dumps(ctx.get("topology", {}))

    # Prepend structured context and memory to the incidents context
    context_prefix = ContextEngine.format_for_prompt(ctx)
    if memory_context:
        context_prefix = memory_context + "\n\n" + context_prefix

    full_incidents_context = (context_prefix + "\n" + active_incidents_text).strip()

    # Audit log
    AuditService.log_audit_event(
        db=db,
        user_name=user["username"],
        role=user["role"],
        action="Copilot Chat Stream",
        ip=request.client.host if request.client else "0.0.0.0",
        details=f"Queried copilot stream: '{message[:50]}...'",
        status="Success"
    )

    # Build explainability metadata (computed before streaming begins)
    matched_scenario_key = ai_engine_root.find_matching_scenario(message)
    routing_score = 5 if routed_persona else 0
    exp = ExplainabilityEngine.build(
        prompt=message,
        persona_selected=session_persona,
        persona_reason=f"Auto-routed to {session_persona}" if routed_persona else f"User selected {session_persona}",
        routing_score=routing_score,
        context=ctx,
        scenario_key=matched_scenario_key,
        memory_context_used=memory_context_used,
    )

    async def sse_event_generator():
        accumulated_text = ""
        async for chunk in AIEngineWrapper.generate_streaming_response(
            prompt_text=message,
            conversation_history=history,
            persona_key=session_persona,
            active_scenario=active_scenario,
            active_incidents_context=full_incidents_context,
            topology_context=topology_context,
            uploaded_logs=req.uploadedLogs,
            uploaded_config=req.uploadedConfig
        ):
            if chunk["text"]:
                accumulated_text += chunk["text"]

            # On final chunk, attach explainability metadata
            if chunk.get("done"):
                chunk["explainability"] = exp

            yield f"data: {json.dumps(chunk)}\n\n"

        # Persist to memory after stream completes
        if accumulated_text:
            MemoryManager.append_message(session_id, "user", message, persona=session_persona, db=db)
            MemoryManager.append_message(session_id, "model", accumulated_text, persona=session_persona, db=db)
            # Store explainability record
            ExplainabilityEngine.store(exp, message, accumulated_text, db=db)

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


@router.post("/clear-chat")
async def clear_chat(
    req: ClearChatRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Phase 3: Clears both in-memory cache and DB history for the session."""
    session_id = req.sessionId
    MemoryManager.clear_session(session_id, db=db)
    return {"status": "success", "message": "Chat history cleared"}


# ============================================================
# Phase 3 – New Intelligence Endpoints
# ============================================================

@router.get("/ai/recommendations")
async def get_ai_recommendations(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 3: Returns proactive AI recommendations generated from live telemetry,
    incident data, and alarm patterns. Feeds the dashboard AI panel.
    """
    try:
        ctx = ContextEngine.build_context(db=db, user=user)
        result = RecommendationsEngine.generate(
            telemetry=ctx.get("telemetry", []),
            active_incidents=ctx.get("active_incidents", []),
            active_alarms=ctx.get("active_alarms", []),
            devices=ctx.get("devices", []),
            db=db,
        )
        return result
    except Exception as e:
        logger.error(f"Recommendations endpoint error: {e}")
        return {
            "recommendations": [],
            "summary": "Recommendations engine encountered an error. Check server logs.",
            "generated_at": "",
            "total_count": 0,
            "critical_count": 0,
            "warning_count": 0,
        }


@router.post("/ai/rca")
async def generate_structured_rca(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 3: Generate a structured, evidence-based Root Cause Analysis.
    Request body: { "alert_type": str, "device_name": str, "incident_id": str (optional) }
    """
    try:
        body = await request.json()
        alert_type = body.get("alert_type", "general alert")
        device_name = body.get("device_name", "Unknown")
        incident_id = body.get("incident_id", "")

        ctx = ContextEngine.build_context(db=db, user=user)

        from ai_engine.rca_engine import RCAEngine
        rca = RCAEngine.generate(
            alert_type=alert_type,
            device_name=device_name,
            incident_id=incident_id,
            telemetry=ctx.get("telemetry", []),
            alarms=ctx.get("active_alarms", []),
            incidents=ctx.get("active_incidents", []),
            topology=ctx.get("topology", {}),
            db=db,
        )

        AuditService.log_audit_event(
            db=db,
            user_name=user["username"],
            role=user["role"],
            action="RCA Generated",
            ip=request.client.host if request.client else "0.0.0.0",
            details=f"Structured RCA for: {alert_type} on {device_name}",
            status="Success"
        )

        return {
            "rca": rca,
            "markdown": RCAEngine.format_as_markdown(rca),
        }
    except Exception as e:
        logger.error(f"RCA endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"RCA generation failed: {e}")


@router.post("/ai/risk-assess")
async def assess_change_risk(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 3: Pre-flight risk assessment on proposed configuration commands.
    Request body: { "commands": str, "device_name": str, "target_devices": list (optional) }
    """
    try:
        body = await request.json()
        commands = body.get("commands", "")
        device_name = body.get("device_name", "Unknown")
        target_devices = body.get("target_devices", None)

        if not commands:
            raise HTTPException(status_code=400, detail="No commands provided for risk assessment")

        from ai_engine.risk_engine import RiskEngine
        risk = RiskEngine.assess(
            commands_text=commands,
            device_name=device_name,
            target_devices=target_devices,
        )

        AuditService.log_audit_event(
            db=db,
            user_name=user["username"],
            role=user["role"],
            action="Risk Assessment",
            ip=request.client.host if request.client else "0.0.0.0",
            details=f"Risk assessed: {risk.get('overall_risk_level','?')} for {device_name}",
            status="Success"
        )

        return {
            "risk": risk,
            "markdown": RiskEngine.format_as_markdown(risk),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk assessment endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Risk assessment failed: {e}")


@router.post("/ai/mop")
async def generate_enterprise_mop(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phase 3: Generate an enterprise-grade Method of Procedure document.
    Request body: { "scenario": str, "commands": str, "device_name": str, "incident_id": str (optional) }
    """
    try:
        body = await request.json()
        scenario = body.get("scenario", "configuration change")
        commands = body.get("commands", "")
        device_name = body.get("device_name", "Unknown")
        incident_id = body.get("incident_id", None)

        # Run risk assessment first
        risk = None
        if commands:
            from ai_engine.risk_engine import RiskEngine
            risk = RiskEngine.assess(commands_text=commands, device_name=device_name)

        from ai_engine.mop_engine import MOPEngine
        mop = MOPEngine.generate(
            scenario_key=scenario,
            command_patch=commands,
            target_device=device_name,
            risk_assessment=risk,
            incident_id=incident_id,
            engineer_name=user.get("username"),
        )

        AuditService.log_audit_event(
            db=db,
            user_name=user["username"],
            role=user["role"],
            action="MOP Generated",
            ip=request.client.host if request.client else "0.0.0.0",
            details=f"Enterprise MOP for: {scenario} on {device_name}",
            status="Success"
        )

        return {
            "mop": mop,
            "markdown": MOPEngine.format_as_markdown(mop),
            "risk": risk,
        }
    except Exception as e:
        logger.error(f"MOP endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"MOP generation failed: {e}")
