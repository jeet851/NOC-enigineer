from fastapi import APIRouter, Depends
from api.deps import get_current_user
from schemas.topology import TopologyGraphResponse
from topology.manager import TopologyManager

router = APIRouter(prefix="/api/topology", tags=["topology"])

topology_manager = TopologyManager()

@router.get("/graph", response_model=TopologyGraphResponse)
async def get_topology_graph(user: dict = Depends(get_current_user)):
    return topology_manager.get_graph()
