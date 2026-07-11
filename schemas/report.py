from pydantic import BaseModel

class GenerateReportRequest(BaseModel):
    scenario: str
    reportType: str  # rca, mop, sop, executive

class GenerateReportResponse(BaseModel):
    markdown: str
