from typing import Optional, List, Any
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import select, desc, asc, or_

class QueryParameters(BaseModel):
    page: int = 1
    limit: int = 50
    sort_by: Optional[str] = None
    order: str = "desc"
    search: Optional[str] = None
    filters: Optional[str] = None  # Expected format: field1:val1,field2:val2

def apply_query_params(stmt, model, params: QueryParameters):
    """
    Applies search, filtering, sorting, and pagination dynamically to a SQLAlchemy select statement.
    """
    # 1. Apply search (checks for model search_fields list)
    if params.search and hasattr(model, "search_fields"):
        search_filters = []
        for field_name in model.search_fields:
            if hasattr(model, field_name):
                field = getattr(model, field_name)
                search_filters.append(field.ilike(f"%{params.search}%"))
        if search_filters:
            stmt = stmt.where(or_(*search_filters))

    # 2. Apply filters
    if params.filters:
        filter_pairs = params.filters.split(",")
        for pair in filter_pairs:
            if ":" in pair:
                field_name, val = pair.split(":", 1)
                if hasattr(model, field_name):
                    field = getattr(model, field_name)
                    # Convert types
                    if val.lower() == "true":
                        val_parsed = True
                    elif val.lower() == "false":
                        val_parsed = False
                    elif val.isdigit():
                        val_parsed = int(val)
                    else:
                        val_parsed = val
                    stmt = stmt.where(field == val_parsed)

    # 3. Apply sorting
    if params.sort_by and hasattr(model, params.sort_by):
        field = getattr(model, params.sort_by)
        if params.order.lower() == "asc":
            stmt = stmt.order_by(asc(field))
        else:
            stmt = stmt.order_by(desc(field))
    elif hasattr(model, "timestamp"):
        stmt = stmt.order_by(desc(model.timestamp))

    # 4. Apply pagination
    skip = (params.page - 1) * params.limit
    stmt = stmt.offset(skip).limit(params.limit)
    return stmt
