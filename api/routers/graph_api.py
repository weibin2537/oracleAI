#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
API接口模块

该模块实现了Oracle存储过程3D调用链分析图谱的API接口，用于前端调用。
"""

import os
import json
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# 导入图谱查询引擎
from graph.queries.graph_queries import GraphQueryEngine

# 配置信息
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# 创建路由器
router = APIRouter(prefix="/api/graph", tags=["graph"])

# 数据模型
class NodeBase(BaseModel):
    id: str
    name: str
    type: str

class SPNode(NodeBase):
    schema: str
    complexity: int = 0
    last_modified: str = ""

class TableNode(NodeBase):
    schema: str
    is_core: bool = False

class EdgeBase(BaseModel):
    source: str
    target: str
    type: str
    confidence: float

class CallsEdge(EdgeBase):
    depth: int
    frequency: int

class ReferencesEdge(EdgeBase):
    operation: str
    is_dynamic: bool

class GraphData(BaseModel):
    nodes: List[Any]
    links: List[Any]

class RiskAssessment(BaseModel):
    name: str
    schema: str
    risk_level: str
    call_chain_complexity: int
    dynamic_sql_count: int
    core_table_count: int
    low_confidence_count: int
    risk_factors: List[Dict[str, Any]]

class ImpactAnalysis(BaseModel):
    sp_name: str
    total_affected: int
    affected_sps: int
    affected_tables: int
    affected_nodes: List[Dict[str, Any]]

class SPDetails(BaseModel):
    id: str
    name: str
    schema: str
    complexity: int = 0
    last_modified: str = ""
    description: str = ""
    called_sps: List[Dict[str, Any]] = []
    referenced_tables: List[Dict[str, Any]] = []
    dyn_referenced_tables: List[Dict[str, Any]] = []

class SearchResult(BaseModel):
    procedures: List[Dict[str, Any]]

# 依赖项
def get_graph_engine():
    """获取图谱查询引擎实例"""
    engine = GraphQueryEngine(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        yield engine
    finally:
        engine.close()

# API路由
@router.get("/procedure/{sp_name}", response_model=SPDetails)
async def get_procedure_details(sp_name: str, engine: GraphQueryEngine = Depends(get_graph_engine)):
    """获取存储过程详细信息"""
    result = engine.get_sp_details(sp_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/call-chain/{sp_name}", response_model=GraphData)
async def get_call_chain(
    sp_name: str, 
    depth: int = Query(3, ge=1, le=5), 
    confidence: float = Query(0.5, ge=0, le=1.0),
    engine: GraphQueryEngine = Depends(get_graph_engine)
):
    """获取存储过程调用链"""
    result = engine.get_call_chain_3d(sp_name, depth, confidence)
    return result

@router.get("/risk/{sp_name}", response_model=RiskAssessment)
async def get_risk_assessment(sp_name: str, engine: GraphQueryEngine = Depends(get_graph_engine)):
    """获取存储过程风险评估"""
    result = engine.get_risk_assessment(sp_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/search", response_model=SearchResult)
async def search_procedures(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    engine: GraphQueryEngine = Depends(get_graph_engine)
):
    """搜索存储过程"""
    procedures = engine.search_procedures(keyword, limit)
    return {"procedures": procedures}

@router.get("/impact/{sp_name}", response_model=ImpactAnalysis)
async def get_impact_analysis(
    sp_name: str,
    depth: int = Query(5, ge=1, le=10),
    engine: GraphQueryEngine = Depends(get_graph_engine)
):
    """获取存储过程影响分析
    
    分析指定存储过程对其他存储过程和表的影响范围，返回受影响的节点列表。
    """
    result = engine.get_impact_analysis(sp_name, depth)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result