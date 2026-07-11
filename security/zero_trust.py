import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ai_engine

class ZeroTrustPolicyManager:
    """
    Enforces security checkpoints like Dual Approvals and command validation.
    """
    @staticmethod
    def validate_deployment_safety(commands: str) -> dict:
        destructive_alerts = ai_engine.check_ai_safety(commands)
        requires_dual_approval = len(destructive_alerts) > 0
        return {
            "destructive_alerts": destructive_alerts,
            "requires_dual_approval": requires_dual_approval
        }

    @staticmethod
    def assert_user_permissions(user_role: str, action: str, details: str = ""):
        # Check standard user role capabilities
        if user_role == "Guest":
            raise PermissionError("Guests are restricted to read-only operation.")
        if user_role == "Network Engineer" and action == "deploy_patch":
            raise PermissionError("Network Engineers require escalation approvals to execute configurations.")
        return True
