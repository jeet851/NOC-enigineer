from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from models.incident import Incident
from database.repositories.incident import IncidentRepository
from datetime import datetime
from typing import List, Optional

class IncidentService:
    incident_repo = IncidentRepository()

    # --- Synchronous Methods (Backward Compatibility) ---

    @staticmethod
    def get_incidents(db: Session) -> List[Incident]:
        return IncidentService.incident_repo.get_all_sorted_sync(db)

    @staticmethod
    def get_active_incidents(db: Session) -> List[Incident]:
        return IncidentService.incident_repo.get_active_sync(db)

    @staticmethod
    def create_incident(
        db: Session,
        incident_id: str,
        severity: str,
        device_name: str,
        site: str,
        vendor: str,
        description: str,
        business_impact: str,
        confidence: str,
        root_cause: str,
        status: str = "Active",
        evidence: Optional[str] = None,
        remediation_commands: Optional[str] = None,
        verification_steps: Optional[str] = None,
        rollback_plan: Optional[str] = None,
        risk_level: Optional[str] = None,
        repair_time: Optional[str] = None,
        engineering_report: Optional[str] = None
    ) -> Incident:
        incident = IncidentService.incident_repo.get_sync(db, incident_id)
        update_data = {
            "severity": severity,
            "description": description,
            "business_impact": business_impact,
            "confidence": confidence,
            "root_cause": root_cause,
            "status": status,
            "timestamp": datetime.utcnow()
        }
        
        if evidence is not None: update_data["evidence"] = evidence
        if remediation_commands is not None: update_data["remediation_commands"] = remediation_commands
        if verification_steps is not None: update_data["verification_steps"] = verification_steps
        if rollback_plan is not None: update_data["rollback_plan"] = rollback_plan
        if risk_level is not None: update_data["risk_level"] = risk_level
        if repair_time is not None: update_data["repair_time"] = repair_time
        if engineering_report is not None: update_data["engineering_report"] = engineering_report

        if incident:
            return IncidentService.incident_repo.update_sync(db, incident, update_data)
        else:
            new_incident = Incident(
                id=incident_id,
                severity=severity,
                device_name=device_name,
                site=site,
                vendor=vendor,
                description=description,
                business_impact=business_impact,
                confidence=confidence,
                root_cause=root_cause,
                status=status,
                timestamp=datetime.utcnow(),
                **{k: v for k, v in update_data.items() if k not in ["severity", "description", "business_impact", "confidence", "root_cause", "status", "timestamp"]}
            )
            return IncidentService.incident_repo.create_sync(db, new_incident)

    @staticmethod
    def resolve_incident(db: Session, incident_id: str) -> bool:
        incident = IncidentService.incident_repo.get_sync(db, incident_id)
        if incident:
            IncidentService.incident_repo.update_sync(db, incident, {"status": "Resolved", "resolved_at": datetime.utcnow()})
            return True
        return False

    # --- Asynchronous Methods (for FastAPI) ---

    @staticmethod
    async def get_incidents_async(db: AsyncSession) -> List[Incident]:
        return await IncidentService.incident_repo.get_all_sorted(db)

    @staticmethod
    async def get_active_incidents_async(db: AsyncSession) -> List[Incident]:
        return await IncidentService.incident_repo.get_active(db)

    @staticmethod
    async def create_incident_async(
        db: AsyncSession,
        incident_id: str,
        severity: str,
        device_name: str,
        site: str,
        vendor: str,
        description: str,
        business_impact: str,
        confidence: str,
        root_cause: str,
        status: str = "Active",
        evidence: Optional[str] = None,
        remediation_commands: Optional[str] = None,
        verification_steps: Optional[str] = None,
        rollback_plan: Optional[str] = None,
        risk_level: Optional[str] = None,
        repair_time: Optional[str] = None,
        engineering_report: Optional[str] = None
    ) -> Incident:
        incident = await IncidentService.incident_repo.get(db, incident_id)
        update_data = {
            "severity": severity,
            "description": description,
            "business_impact": business_impact,
            "confidence": confidence,
            "root_cause": root_cause,
            "status": status,
            "timestamp": datetime.utcnow()
        }
        
        if evidence is not None: update_data["evidence"] = evidence
        if remediation_commands is not None: update_data["remediation_commands"] = remediation_commands
        if verification_steps is not None: update_data["verification_steps"] = verification_steps
        if rollback_plan is not None: update_data["rollback_plan"] = rollback_plan
        if risk_level is not None: update_data["risk_level"] = risk_level
        if repair_time is not None: update_data["repair_time"] = repair_time
        if engineering_report is not None: update_data["engineering_report"] = engineering_report

        if incident:
            return await IncidentService.incident_repo.update(db, incident, update_data)
        else:
            new_incident = Incident(
                id=incident_id,
                severity=severity,
                device_name=device_name,
                site=site,
                vendor=vendor,
                description=description,
                business_impact=business_impact,
                confidence=confidence,
                root_cause=root_cause,
                status=status,
                timestamp=datetime.utcnow(),
                **{k: v for k, v in update_data.items() if k not in ["severity", "description", "business_impact", "confidence", "root_cause", "status", "timestamp"]}
            )
            return await IncidentService.incident_repo.create(db, new_incident)

    @staticmethod
    async def resolve_incident_async(db: AsyncSession, incident_id: str) -> bool:
        incident = await IncidentService.incident_repo.get(db, incident_id)
        if incident:
            await IncidentService.incident_repo.update(db, incident, {"status": "Resolved", "resolved_at": datetime.utcnow()})
            return True
        return False
