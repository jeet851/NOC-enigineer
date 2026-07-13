"""
Explainability Wrapper – Phase 3 Intelligence Enhancement
Wraps every AI response with structured metadata explaining WHY the AI
reached its conclusion: evidence considered, telemetry analysed, related
alerts, historical comparison, selected persona, and confidence score.
Eliminates "black box" AI responses across Dashboard, CLI, and Slack.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("noc.explainability")


# ---------------------------------------------------------------------------
# Explainability schema
# ---------------------------------------------------------------------------

def _empty_explainability() -> Dict[str, Any]:
    return {
        "generated_at": "",
        "persona_selected": "",
        "persona_reason": "",
        "routing_confidence": 0,
        "context_sources_used": [],
        "telemetry_devices_analysed": [],
        "active_incidents_referenced": [],
        "alarms_referenced": [],
        "historical_incidents_matched": [],
        "memory_context_used": False,
        "scenario_matched": None,
        "overall_confidence": 0,
        "reasoning_summary": "",
    }


# ---------------------------------------------------------------------------
# Explainability Engine
# ---------------------------------------------------------------------------

class ExplainabilityEngine:
    """
    Produces structured explainability metadata attached to every AI response.
    Eliminates opaque AI outputs and provides operators with full audit trails.
    """

    @staticmethod
    def build(
        prompt: str,
        persona_selected: str,
        persona_reason: str = "",
        routing_score: int = 0,
        context: Optional[Dict] = None,
        scenario_key: Optional[str] = None,
        memory_context_used: bool = False,
        rca_performed: bool = False,
        risk_assessed: bool = False,
        response_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build the explainability block for a single AI interaction.

        Parameters
        ----------
        prompt            : The user's query
        persona_selected  : Persona key chosen by the router
        persona_reason    : Human-readable reason for persona selection
        routing_score     : Confidence score from IntentRouter
        context           : AIContext dict from ContextEngine
        scenario_key      : Matched scenario key (if any)
        memory_context_used : Whether prior conversation memory was injected
        rca_performed     : Whether structured RCA was run
        risk_assessed     : Whether risk assessment was run
        response_text     : The generated response (for confidence estimation)
        """
        exp = _empty_explainability()
        exp["generated_at"] = datetime.utcnow().isoformat()

        # Persona selection
        exp["persona_selected"] = persona_selected
        exp["persona_reason"] = persona_reason or f"Routed to {persona_selected} persona"
        exp["routing_confidence"] = min(routing_score * 5 + 30, 99) if routing_score > 0 else 50

        # Context sources used
        sources = []
        if context:
            telemetry = context.get("telemetry", [])
            if telemetry:
                sources.append(f"Telemetry ({len(telemetry)} device readings)")
                exp["telemetry_devices_analysed"] = [
                    t.get("device_name", "?") for t in telemetry[:8]
                ]

            incidents = context.get("active_incidents", [])
            if incidents:
                sources.append(f"Active Incidents ({len(incidents)} open)")
                exp["active_incidents_referenced"] = [
                    f"{i.get('id','?')} ({i.get('severity','?')})" for i in incidents[:5]
                ]

            alarms = context.get("active_alarms", [])
            if alarms:
                sources.append(f"Active Alarms ({len(alarms)})")
                exp["alarms_referenced"] = [
                    f"{a.get('source','?')}: {a.get('metric','?')}={a.get('value','?')}"
                    for a in alarms[:5]
                ]

            devices = context.get("devices", [])
            if devices:
                sources.append(f"Device Inventory ({len(devices)} devices)")

            topology = context.get("topology", {})
            if topology.get("nodes") or topology.get("devices"):
                sources.append("Topology Graph")

            automation = context.get("recent_automation", [])
            if automation:
                sources.append(f"Recent Automation ({len(automation)} events)")

            drift = context.get("config_drift_warnings", [])
            if drift:
                sources.append(f"Config Baseline ({len(drift)} drift alerts)")

        if memory_context_used:
            sources.append("Conversation Memory (prior session context)")
            exp["memory_context_used"] = True

        if scenario_key:
            sources.append(f"Scenario Template ({scenario_key})")
            exp["scenario_matched"] = scenario_key

        if rca_performed:
            sources.append("Structured RCA Engine (8-step analysis)")

        if risk_assessed:
            sources.append("Risk Assessment Engine")

        exp["context_sources_used"] = sources

        # Overall confidence estimation
        base_confidence = 65
        if routing_score > 3:
            base_confidence += 10
        if context and context.get("telemetry"):
            base_confidence += 8
        if context and context.get("active_incidents"):
            base_confidence += 5
        if scenario_key:
            base_confidence += 7
        if memory_context_used:
            base_confidence += 5
        if rca_performed:
            base_confidence += 10
        exp["overall_confidence"] = min(base_confidence, 98)

        # Reasoning summary
        exp["reasoning_summary"] = ExplainabilityEngine._build_summary(exp, prompt)

        return exp

    @staticmethod
    def _build_summary(exp: Dict, prompt: str) -> str:
        parts = []

        # Persona
        parts.append(f"Assigned to **{exp['persona_selected']}** persona ({exp['persona_reason']}).")

        # Data sources
        sources = exp.get("context_sources_used", [])
        if sources:
            parts.append(f"Analysis used: {'; '.join(sources)}.")

        # Telemetry
        devices = exp.get("telemetry_devices_analysed", [])
        if devices:
            parts.append(f"Telemetry reviewed for: {', '.join(devices)}.")

        # Incidents
        incidents = exp.get("active_incidents_referenced", [])
        if incidents:
            parts.append(f"Active incidents cross-referenced: {', '.join(incidents)}.")

        # Memory
        if exp.get("memory_context_used"):
            parts.append("Prior conversation memory injected for follow-up context.")

        # Confidence
        parts.append(f"Overall response confidence: **{exp['overall_confidence']}%**.")

        return " ".join(parts)

    @staticmethod
    def format_for_response(exp: Dict, include_in_body: bool = False) -> str:
        """
        Format the explainability block for inclusion in the AI response body
        or as a collapsible metadata section.
        """
        if not include_in_body:
            return ""  # metadata only mode — included in JSON chunk

        lines = [
            "",
            "---",
            "## 🔍 AI Reasoning & Explainability",
            f"**Persona:** {exp.get('persona_selected', 'N/A')} — {exp.get('persona_reason', '')}",
            f"**Confidence Score:** {exp.get('overall_confidence', 0)}%",
            "",
            "**Evidence Considered:**",
        ]
        for src in exp.get("context_sources_used", []):
            lines.append(f"- {src}")

        devices = exp.get("telemetry_devices_analysed", [])
        if devices:
            lines.append(f"\n**Telemetry Devices Analysed:** {', '.join(devices)}")

        incidents = exp.get("active_incidents_referenced", [])
        if incidents:
            lines.append(f"**Incidents Referenced:** {', '.join(incidents)}")

        alarms = exp.get("alarms_referenced", [])
        if alarms:
            lines += ["**Alarms Referenced:**"] + [f"- {a}" for a in alarms]

        if exp.get("memory_context_used"):
            lines.append("**Memory:** Prior session context injected to resolve follow-up question.")

        if exp.get("scenario_matched"):
            lines.append(f"**Scenario Template:** {exp['scenario_matched']}")

        lines += [
            "",
            f"*Generated: {exp.get('generated_at','')[:19]} | "
            f"Routing confidence: {exp.get('routing_confidence',0)}%*",
        ]

        return "\n".join(lines)

    @staticmethod
    def store(exp: Dict, prompt: str, response: str, user_id: Optional[int] = None, db=None) -> None:
        """Persist explainability record to the AIAnalysisHistory table."""
        if db is None:
            return
        try:
            from models.ai_analysis import AIAnalysisHistory

            record = AIAnalysisHistory(
                prompt=prompt[:500],
                response=response[:2000],
                scenario=exp.get("scenario_matched"),
                safety_status=f"Confidence: {exp.get('overall_confidence', 0)}% | Persona: {exp.get('persona_selected','')}",
                user_id=user_id,
            )
            db.add(record)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist explainability record: {e}")
            try:
                db.rollback()
            except Exception:
                pass
