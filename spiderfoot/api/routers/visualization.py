"""
Visualization endpoints for SpiderFoot API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, JSONResponse
from typing import Optional, List
import json
import logging

from ..dependencies import get_app_config, optional_auth
from spiderfoot import SpiderFootDb, SpiderFootHelpers

router = APIRouter()
logger = logging.getLogger(__name__)
optional_auth_dep = Depends(optional_auth)


@router.get("/visualization/graph/{scan_id}")
async def get_scan_graph_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    format: str = Query("json", description="Output format: json, gexf"),
    filter_type: Optional[str] = Query(None, description="Filter by event type"),
    include_internal: bool = Query(False, description="Include internal events")
):
    """
    Generate graph visualization data for a scan.
    
    Args:
        scan_id: Scan identifier
        format: Output format (json or gexf)
        filter_type: Optional event type filter
        include_internal: Whether to include internal events
        
    Returns:
        Graph data in requested format
    """
    try:
        config = get_app_config()
        dbh = SpiderFootDb(config.get_config())
        
        # Validate scan exists
        scan_info = dbh.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get scan data for visualization
        scan_results = dbh.scanResultEvent(scan_id, filter_type)
        
        if format.lower() == "gexf":
            # Generate GEXF format
            graph_data = SpiderFootHelpers.buildGraphGexf(
                [scan_id], 
                scan_results,
                include_internal
            )
            return Response(
                content=graph_data,
                media_type="application/xml",
                headers={"Content-Disposition": f"attachment; filename=scan_{scan_id}_graph.gexf"}
            )
        else:
            # Generate JSON format
            graph_data = SpiderFootHelpers.buildGraphJson(
                [scan_id],
                scan_results, 
                include_internal
            )
            return JSONResponse(content=json.loads(graph_data) if isinstance(graph_data, str) else graph_data)
            
    except Exception as e:
        logger.error(f"Failed to generate graph for scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate graph: {e}")


@router.get("/visualization/graph/multi")
async def get_multi_scan_graph_data(
    scan_ids: str = Query(..., description="Comma-separated scan IDs"),
    api_key: str = optional_auth_dep,
    format: str = Query("gexf", description="Output format: json, gexf"),
    filter_type: Optional[str] = Query(None, description="Filter by event type"),
    include_internal: bool = Query(False, description="Include internal events")
):
    """
    Generate graph visualization data for multiple scans.
    
    Args:
        scan_ids: Comma-separated list of scan IDs
        format: Output format (json or gexf)
        filter_type: Optional event type filter
        include_internal: Whether to include internal events
        
    Returns:
        Combined graph data in requested format
    """
    try:
        config = get_app_config()
        dbh = SpiderFootDb(config.get_config())
        
        # Parse scan IDs
        scan_list = [s.strip() for s in scan_ids.split(',') if s.strip()]
        if not scan_list:
            raise HTTPException(status_code=400, detail="No valid scan IDs provided")
        
        # Validate scans exist
        all_results = []
        for scan_id in scan_list:
            scan_info = dbh.scanInstanceGet(scan_id)
            if not scan_info:
                logger.warning(f"Scan {scan_id} not found, skipping")
                continue
            
            scan_results = dbh.scanResultEvent(scan_id, filter_type)
            all_results.extend(scan_results)
        
        if not all_results:
            raise HTTPException(status_code=404, detail="No valid scans found")
        
        if format.lower() == "gexf":
            # Generate GEXF format
            graph_data = SpiderFootHelpers.buildGraphGexf(
                scan_list,
                all_results,
                include_internal
            )
            return Response(
                content=graph_data,
                media_type="application/xml",
                headers={"Content-Disposition": "attachment; filename=multi_scan_graph.gexf"}
            )
        else:
            # Generate JSON format
            graph_data = SpiderFootHelpers.buildGraphJson(
                scan_list,
                all_results,
                include_internal
            )
            return JSONResponse(content=json.loads(graph_data) if isinstance(graph_data, str) else graph_data)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate multi-scan graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate graph: {e}")


@router.get("/visualization/summary/{scan_id}")
async def get_scan_summary_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    group_by: str = Query("type", description="Group results by: type, module, risk")
):
    """
    Get statistical summary data for visualization.
    
    Args:
        scan_id: Scan identifier
        group_by: How to group the data (type, module, risk)
        
    Returns:
        Summary statistics for visualization
    """
    try:
        config = get_app_config()
        dbh = SpiderFootDb(config.get_config())
        
        # Validate scan exists
        scan_info = dbh.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get summary data
        summary_data = dbh.scanResultSummary(scan_id, group_by)
        
        # Process for visualization
        chart_data = {
            "labels": [],
            "values": [],
            "total": 0
        }
        
        for item in summary_data:
            if group_by == "type":
                label = item[0]  # event type
                value = item[4]  # count
            elif group_by == "module":
                label = item[1]  # module name
                value = item[4]  # count
            else:  # risk
                label = item[3] if len(item) > 3 else "Unknown"  # risk level
                value = item[4] if len(item) > 4 else 1  # count
            
            chart_data["labels"].append(label)
            chart_data["values"].append(value)
            chart_data["total"] += value
        
        return {
            "scan_id": scan_id,
            "group_by": group_by,
            "data": chart_data,
            "scan_info": {
                "name": scan_info[0],
                "target": scan_info[1],
                "status": scan_info[5] if len(scan_info) > 5 else "Unknown"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get summary data for scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get summary data: {e}")


@router.get("/visualization/timeline/{scan_id}")
async def get_scan_timeline_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    interval: str = Query("hour", description="Time interval: hour, day, week"),
    event_type: Optional[str] = Query(None, description="Filter by event type")
):
    """
    Get timeline data for scan events.
    
    Args:
        scan_id: Scan identifier
        interval: Time grouping interval
        event_type: Optional event type filter
        
    Returns:
        Timeline data for visualization
    """
    try:
        config = get_app_config()
        dbh = SpiderFootDb(config.get_config())
        
        # Validate scan exists
        scan_info = dbh.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get scan events with timestamps
        scan_results = dbh.scanResultEvent(scan_id, event_type)
        
        # Group by time interval
        timeline_data = {}
        for result in scan_results:
            timestamp = result[0]  # Event timestamp
            
            # Convert to appropriate interval
            if interval == "hour":
                time_key = timestamp.strftime("%Y-%m-%d %H:00")
            elif interval == "day":
                time_key = timestamp.strftime("%Y-%m-%d")
            elif interval == "week":
                # Get week start (Monday)
                week_start = timestamp - timedelta(days=timestamp.weekday())
                time_key = week_start.strftime("%Y-%m-%d")
            else:
                time_key = timestamp.strftime("%Y-%m-%d %H:%M")
            
            if time_key not in timeline_data:
                timeline_data[time_key] = 0
            timeline_data[time_key] += 1
        
        # Convert to list format for charts
        sorted_timeline = sorted(timeline_data.items())
        
        return {
            "scan_id": scan_id,
            "interval": interval,
            "timeline": {
                "timestamps": [item[0] for item in sorted_timeline],
                "counts": [item[1] for item in sorted_timeline]
            },
            "total_events": sum(timeline_data.values()),
            "scan_info": {
                "name": scan_info[0],
                "target": scan_info[1],
                "status": scan_info[5] if len(scan_info) > 5 else "Unknown"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get timeline data for scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get timeline data: {e}")


@router.get("/visualization/heatmap/{scan_id}")
async def get_scan_heatmap_data(
    scan_id: str,
    api_key: str = optional_auth_dep,
    dimension_x: str = Query("module", description="X-axis dimension: module, type, risk"),
    dimension_y: str = Query("type", description="Y-axis dimension: module, type, risk")
):
    """
    Get heatmap data for scan results.
    
    Args:
        scan_id: Scan identifier
        dimension_x: X-axis grouping dimension
        dimension_y: Y-axis grouping dimension
        
    Returns:
        Heatmap data for visualization
    """
    try:
        config = get_app_config()
        dbh = SpiderFootDb(config.get_config())
        
        # Validate scan exists
        scan_info = dbh.scanInstanceGet(scan_id)
        if not scan_info:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Get scan results
        scan_results = dbh.scanResultEvent(scan_id)
        
        # Build heatmap matrix
        heatmap_data = {}
        x_labels = set()
        y_labels = set()
        
        for result in scan_results:
            # Extract dimensions based on parameters
            if dimension_x == "module":
                x_val = result[2]  # Module name
            elif dimension_x == "type":
                x_val = result[3]  # Event type
            else:  # risk
                x_val = "Medium"  # Default risk level
            
            if dimension_y == "module":
                y_val = result[2]  # Module name
            elif dimension_y == "type":
                y_val = result[3]  # Event type
            else:  # risk
                y_val = "Medium"  # Default risk level
            
            x_labels.add(x_val)
            y_labels.add(y_val)
            
            if x_val not in heatmap_data:
                heatmap_data[x_val] = {}
            if y_val not in heatmap_data[x_val]:
                heatmap_data[x_val][y_val] = 0
            
            heatmap_data[x_val][y_val] += 1
        
        # Convert to matrix format
        x_labels_list = sorted(x_labels)
        y_labels_list = sorted(y_labels)
        
        matrix = []
        for y_label in y_labels_list:
            row = []
            for x_label in x_labels_list:
                value = heatmap_data.get(x_label, {}).get(y_label, 0)
                row.append(value)
            matrix.append(row)
        
        return {
            "scan_id": scan_id,
            "dimensions": {
                "x": dimension_x,
                "y": dimension_y
            },
            "heatmap": {
                "x_labels": x_labels_list,
                "y_labels": y_labels_list,
                "matrix": matrix
            },
            "scan_info": {
                "name": scan_info[0],
                "target": scan_info[1],
                "status": scan_info[5] if len(scan_info) > 5 else "Unknown"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get heatmap data for scan {scan_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get heatmap data: {e}")
