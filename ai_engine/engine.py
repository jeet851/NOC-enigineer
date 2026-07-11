import sys
import os
import importlib.util

# Load root-level ai_engine.py directly to bypass naming conflicts
spec = importlib.util.spec_from_file_location(
    "ai_engine_root",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai_engine.py"))
)
ai_engine_root = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_engine_root)

class AIEngineWrapper:
    """
    Evaluates monitoring alarms against healing policies and security thresholds.
    """
    def __init__(self, healing_policy: str = "approval", severity_threshold: int = 3):
        self.healing_policy = healing_policy  # "approval" or "autonomous"
        self.severity_threshold = severity_threshold  # 1=Info, 2=Warning, 3=Critical

    def should_auto_heal(self, severity_label: str) -> bool:
        severity_map = {
            "info": 1,
            "warning": 2,
            "critical": 3,
            "disaster": 4
        }
        severity_num = severity_map.get(severity_label.lower(), 2)
        if self.healing_policy == "autonomous" and severity_num >= self.severity_threshold:
            return True
        return False

    def evaluate_incident(self, device_name: str, metric: str, value: str) -> dict:
        recommendation = "Run standard diagnostics sweep."
        playbook = "standard_diagnostic_playbook"

        metric_lower = metric.lower()
        if "vpn" in metric_lower or "tunnel" in metric_lower:
            recommendation = "Clear active crypto sessions and verify phase 1 ISAKMP keys."
            playbook = "vpn_reset_playbook"
        elif "cpu" in metric_lower:
            recommendation = "Inspect process list sorted by CPU load and terminate rogue worker PIDs."
            playbook = "cpu_mitigation_playbook"
        elif "disk" in metric_lower or "partition" in metric_lower:
            recommendation = "Audit and compress historic system log files."
            playbook = "log_cleanup_playbook"
        elif "ssh" in metric_lower or "spray" in metric_lower:
            recommendation = "Apply perimeter firewall access-list blocking malicious source IP blocks."
            playbook = "firewall_acl_block"

        return {
            "root_cause_candidate": f"Potential issue on {device_name} relating to {metric}.",
            "recommended_action": recommendation,
            "playbook_reference": playbook
        }

    @staticmethod
    def generate_response(prompt_text: str, conversation_history: list, persona_key: str, active_scenario: str) -> str:
        return ai_engine_root.generate_ai_response(
            prompt_text=prompt_text,
            conversation_history=conversation_history,
            persona_key=persona_key,
            active_scenario=active_scenario
        )

    @staticmethod
    async def generate_streaming_response(
        prompt_text: str,
        conversation_history: list,
        persona_key: str,
        active_scenario: str,
        active_incidents_context: str = None,
        topology_context: str = None,
        uploaded_logs: str = None,
        uploaded_config: str = None
    ):
        async for chunk in ai_engine_root.generate_streaming_response(
            prompt_text=prompt_text,
            conversation_history=conversation_history,
            persona_key=persona_key,
            active_scenario=active_scenario,
            active_incidents_context=active_incidents_context,
            topology_context=topology_context,
            uploaded_logs=uploaded_logs,
            uploaded_config=uploaded_config
        ):
            yield chunk

    @staticmethod
    def validate_commands(commands_text: str, device_type: str = "Cisco"):
        return ai_engine_root.validate_commands(commands_text, device_type)

    @staticmethod
    def run_simulation(commands_text: str, device_type: str = "Cisco"):
        return ai_engine_root.run_simulation(commands_text, device_type)

    @staticmethod
    def check_safety(commands_text: str) -> list:
        return ai_engine_root.check_ai_safety(commands_text)

    @staticmethod
    def check_injection(text: str) -> bool:
        return ai_engine_root.check_prompt_injection(text)

    @staticmethod
    def auto_route_intent(text: str) -> str:
        return ai_engine_root.auto_route_intent(text)

    @staticmethod
    def find_matching_scenario(text: str) -> str:
        return ai_engine_root.find_matching_scenario(text)
