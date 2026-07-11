import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.query_params import QueryParameters, apply_query_params
from models.device import Device
from sqlalchemy import select

# 1. Test standard health and metrics endpoints via the new v1 versioned API path
def test_v1_health_and_metrics_endpoints(client: TestClient):
    # Test v1 health check
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert "status" in health_data
    assert "services" in health_data
    assert health_data["services"]["database"] == "Healthy"

    # Test v1 metrics
    metrics_resp = client.get("/api/v1/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert "process_uptime_seconds" in metrics_data
    assert "system_cpu_usage_percent" in metrics_data
    assert "active_threads_count" in metrics_data

# 2. Test the query parameters helper function logic
def test_query_params_parser():
    params = QueryParameters(
        page=2,
        limit=10,
        sort_by="name",
        order="asc",
        search="edge",
        filters="status:Healthy,vendor:Cisco"
    )
    
    # Assert model parameters are parsed correctly
    assert params.page == 2
    assert params.limit == 10
    assert params.sort_by == "name"
    assert params.order == "asc"
    assert params.search == "edge"
    assert params.filters == "status:Healthy,vendor:Cisco"

    # Verify query generation applying parameters dynamically
    stmt = select(Device)
    stmt = apply_query_params(stmt, Device, params)
    
    # Check that offsets and limits compile correctly in the statement
    stmt_str = str(stmt)
    assert "LIMIT" in stmt_str or "limit" in stmt_str.lower()
    assert "OFFSET" in stmt_str or "offset" in stmt_str.lower()
