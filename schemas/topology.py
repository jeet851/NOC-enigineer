from pydantic import BaseModel
from typing import List, Dict, Any

class TopologyNodeSchema(BaseModel):
    name: str
    label: str
    ip: str
    vendor: str

class TopologyEdgeSchema(BaseModel):
    source: str
    target: str
    type: str
    details: str

class TopologyGraphResponse(BaseModel):
    nodes: List[TopologyNodeSchema]
    edges: List[TopologyEdgeSchema]
