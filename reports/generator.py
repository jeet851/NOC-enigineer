import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import report_generator

class SecurityReportGenerator:
    @staticmethod
    def generate_rca(scenario: str, incident_details: dict) -> str:
        return report_generator.ReportGenerator.generate_rca(scenario, incident_details)

    @staticmethod
    def generate_mop(scenario: str, remediation_plan: str, device: str) -> str:
        return report_generator.ReportGenerator.generate_mop(scenario, remediation_plan, device)

    @staticmethod
    def generate_sop(scenario: str) -> str:
        return report_generator.ReportGenerator.generate_sop(scenario)

    @staticmethod
    def generate_executive_summary(scores: dict, incident_count: int) -> str:
        return report_generator.ReportGenerator.generate_executive_summary(scores, incident_count)
