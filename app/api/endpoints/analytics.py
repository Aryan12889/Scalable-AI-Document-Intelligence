from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.db import get_timeseries_stats

router = APIRouter()

@router.get("/stats")
async def get_analytics_stats(
    range: str = Query("7d", description="Time range for analytics (today, 7d, 30d, custom)"),
    start: Optional[str] = Query(None, description="Start date for custom range (ISO)"),
    end: Optional[str] = Query(None, description="End date for custom range (ISO)")
):
    """
    Retrieve aggregated analytics metrics for the dashboard with dynamic time range.
    """
    try:
        stats = get_timeseries_stats(range_type=range, custom_start=start, custom_end=end)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
