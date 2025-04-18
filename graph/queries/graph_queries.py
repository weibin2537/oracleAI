#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图谱查询模块

该模块实现了Oracle存储过程调用链图谱的高级查询功能，支持调用链分析和风险评估。
"""

import os
import json
from typing import Dict, List, Any, Optional, Tuple
from neo4j import GraphDatabase


class GraphQueryEngine:
    """图谱查询引擎类"""
    
    def __init__(self, uri: str, username: str, password: str):
        """初始化图谱查询引擎
        
        Args:
            uri: Neo4j数据库URI
            username: 数据库用户名
            password: 数据库密码
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
    
    def close(self) -> None:
        """关闭数据库连接"""
        self.driver.close()
    
    def get_sp_details(self, sp_name: str) -> Dict[str, Any]:
        """获取存储过程详细信息
        
        Args:
            sp_name: 存储过程名称
            
        Returns:
            存储过程详细信息
        """
        with self.driver.session() as session:
            result = session.read_transaction(self._get_sp_details_tx, sp_name)
            return result
    
    def _get_sp_details_tx(self, tx, sp_name: str) -> Dict[str, Any]:
        """获取存储过程详细信息的事务函数"""
        query = """
        MATCH (sp:SP_Node {name: $sp_name})
        OPTIONAL MATCH (sp)-[call:CALLS]->(callee:SP_Node)
        OPTIONAL MATCH (sp)-[ref:REFERENCES]->(table:Table_Node)
        OPTIONAL MATCH (sp)-[dyn_ref:DYN_REFERENCES]->(dyn_table:DYN_Table_Node)
        RETURN 
            sp,
            collect(DISTINCT callee) AS callees,
            collect(DISTINCT table) AS tables,
            collect(DISTINCT dyn_table) AS dyn_tables,
            collect(DISTINCT call) AS call_rels,
            collect(DISTINCT ref) AS ref_rels,
            collect(DISTINCT dyn_ref) AS dyn_ref_rels
        """
        
        result = tx.run(query, sp_name=sp_name)
        record = result.single()
        
        if not record or not record["sp"]:
            return {"error": f"存储过程 {sp_name} 不存在"}
        
        sp = record["sp"]
        callees = record["callees"]
        tables = record["tables"]
        dyn_tables = record["dyn_tables"]
        call_rels = record["call_rels"]
        ref_rels = record["ref_rels"]
        dyn_ref_rels = record["dyn_ref_rels"]
        
        # 处理调用的存储过程
        called_sps = []
        for i, callee in enumerate(callees):
            if callee is None:
                continue
            called_sps.append({
                "id": callee.id,
                "name": callee["name"],
                "schema": callee.get("schema", ""),
                "relationship": dict(call_rels[i]) if i < len(call_rels) and call_rels[i] is not None else {}
            })
        
        # 处理引用的表
        referenced_tables = []
        for i, table in enumerate(tables):
            if table is None:
                continue
            referenced_tables.append({
                "id": table.id,
                "name": table["name"],
                "schema": table.get("schema", ""),
                "relationship": dict(ref_rels[i]) if i < len(ref_rels) and ref_rels[i] is not None else {}
            })
        
        # 处理动态引用的表
        dyn_referenced_tables = []
        for i, dyn_table in enumerate(dyn_tables):
            if dyn_table is None:
                continue
            dyn_referenced_tables.append({
                "id": dyn_table.id,
                "pattern": dyn_table["pattern"],
                "variables": json.loads(dyn_table.get("variables", "[]")),
                "relationship": dict(dyn_ref_rels[i]) if i < len(dyn_ref_rels) and dyn_ref_rels[i] is not None else {}
            })
        
        return {
            "id": sp.id,
            "name": sp["name"],
            "schema": sp.get("schema", ""),
            "complexity": sp.get("complexity", 0),
            "last_modified": sp.get("last_modified", ""),
            "description": sp.get("description", ""),
            "called_sps": called_sps,
            "referenced_tables": referenced_tables,
            "dyn_referenced_tables": dyn_referenced_tables
        }
    
    def get_call_chain_3d(self, sp_name: str, max_depth: int = 3, min_confidence: float = 0.5) -> Dict[str, Any]:
        """获取存储过程3D调用链
        
        Args:
            sp_name: 存储过程名称
            max_depth: 最大调用深度
            min_confidence: 最小置信度
            
        Returns:
            3D调用链信息，适用于前端3D可视化
        """
        with self.driver.session() as session:
            result = session.read_transaction(self._get_call_chain_3d_tx, sp_name, max_depth, min_confidence)
            return result
    
    def _get_call_chain_3d_tx(self, tx, sp_name: str, max_depth: int, min_confidence: float) -> Dict[str, Any]:
        """获取3D调用链的事务函数"""
        query = """
        MATCH path = (start:SP_Node {name: $sp_name})-[call:CALLS*1..%d]->(sp:SP_Node)
        WHERE ALL(r IN call WHERE r.confidence >= $min_confidence)
        WITH path, sp
        OPTIONAL MATCH (sp)-[ref:REFERENCES]->(table:Table_Node)
        WHERE ref.confidence >= $min_confidence
        RETURN path, sp, collect(DISTINCT ref) as refs, collect(DISTINCT table) as tables
        """ % max_depth
        
        result = tx.run(query, sp_name=sp_name, min_confidence=min_confidence)
        
        # 处理结果为3D可视化格式
        nodes = []
        links = []
        node_ids = set()
        
        for record in result:
            path = record["path"]
            sp = record["sp"]
            refs = record["refs"]
            tables = record["tables"]
            
            # 添加路径中的所有节点
            for node in path.nodes:
                if node.id not in node_ids:
                    node_ids.add(node.id)
                    nodes.append({
                        "id": str(node.id),
                        "name": node["name"],
                        "schema": node.get("schema", ""),
                        "type": "SP",
                        "complexity": node.get("complexity", 1),
                        "group": 1  # 存储过程组
                    })
            
            # 添加路径中的所有关系
            for rel in path.relationships:
                links.append({
                    "source": str(rel.start_node.id),
                    "target": str(rel.end_node.id),
                    "type": "CALLS",
                    "depth": rel.get("depth", 1),
                    "confidence": rel.get("confidence", 1.0),
                    "value": rel.get("frequency", 1)  # 用于3D可视化的连线粗细
                })
            
            # 添加表节点和引用关系
            for i, table in enumerate(tables):
                if table is None:
                    continue
                    
                if table.id not in node_ids:
                    node_ids.add(table.id)
                    nodes.append({
                        "id": str(table.id),
                        "name": table["name"],
                        "schema": table.get("schema", ""),
                        "type": "TABLE",
                        "is_core": table.get("is_core", False),
                        "group": 2  # 表组
                    })
                
                if i < len(refs) and refs[i] is not None:
                    ref = refs[i]
                    links.append({
                        "source": str(ref.start_node.id),
                        "target": str(ref.end_node.id),
                        "type": "REFERENCES",
                        "operation": ref.get("operation", "SELECT"),
                        "confidence": ref.get("confidence", 1.0),
                        "value": 1  # 默认连线粗细
                    })
        
        return {
            "nodes": nodes,
            "links": links
        }
    
    def get_risk_assessment(self, sp_name: str) -> Dict[str, Any]:
        """获取存储过程风险评估
        
        Args:
            sp_name: 存储过程名称
            
        Returns:
            风险评估信息
        """
        with self.driver.session() as session:
            result = session.read_transaction(self._get_risk_assessment_tx, sp_name)
            return result
    
    def _get_risk_assessment_tx(self, tx, sp_name: str) -> Dict[str, Any]:
        """获取风险评估的事务函数"""
        query = """
        MATCH (sp:SP_Node {name: $sp_name})
        
        // 计算调用链复杂度
        OPTIONAL MATCH path = (sp)-[:CALLS*1..5]->()
        WITH sp, count(path) AS call_chain_complexity
        
        // 计算动态SQL风险
        OPTIONAL MATCH (sp)-[dyn:DYN_REFERENCES]->()
        WITH sp, call_chain_complexity, count(dyn) AS dynamic_sql_count
        
        // 计算核心表访问
        OPTIONAL MATCH (sp)-[:REFERENCES]->(table:Table_Node)
        WHERE table.is_core = true
        WITH sp, call_chain_complexity, dynamic_sql_count, count(table) AS core_table_count
        
        // 计算低置信度关系
        OPTIONAL MATCH (sp)-[r]->()
        WHERE r.confidence < 0.7
        WITH sp, call_chain_complexity, dynamic_sql_count, core_table_count, count(r) AS low_confidence_count
        
        RETURN 
            sp.name AS name,
            sp.schema AS schema,
            call_chain_complexity,
            dynamic_sql_count,
            core_table_count,
            low_confidence_count,
            CASE 
                WHEN dynamic_sql_count > 5 OR core_table_count > 3 OR low_confidence_count > 2 THEN 'HIGH'
                WHEN dynamic_sql_count > 2 OR core_table_count > 1 OR low_confidence_count > 0 THEN 'MEDIUM'
                ELSE 'LOW'
            END AS risk_level
        """
        
        result = tx.run(query, sp_name=sp_name)
        record = result.single()
        
        if not record:
            return {"error": f"存储过程 {sp_name} 不存在"}
        
        return {
            "name": record["name"],
            "schema": record["schema"],
            "call_chain_complexity": record["call_chain_complexity"],
            "dynamic_sql_count": record["dynamic_sql_count"],
            "core_table_count": record["core_table_count"],
            "low_confidence_count": record["low_confidence_count"],
            "risk_level": record["risk_level"],
            "risk_factors": [
                {"name": "调用链复杂度", "value": record["call_chain_complexity"], "threshold": 10},
                {"name": "动态SQL数量", "value": record["dynamic_sql_count"], "threshold": 5},
                {"name": "核心表访问", "value": record["core_table_count"], "threshold": 3},
                {"name": "低置信度关系", "value": record["low_confidence_count"], "threshold": 2}
            ]
        }
    
    def search_procedures(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索存储过程
        
        Args:
            keyword: 关键字
            limit: 返回结果限制
            
        Returns:
            匹配的存储过程列表
        """
        with self.driver.session() as session:
            result = session.read_transaction(self._search_procedures_tx, keyword, limit)
            return result
    
    def _search_procedures_tx(self, tx, keyword: str, limit: int) -> List[Dict[str, Any]]:
        """搜索存储过程的事务函数"""
        query = """
        MATCH (sp:SP_Node)
        WHERE sp.name CONTAINS $keyword OR sp.description CONTAINS $keyword
        RETURN sp
        ORDER BY sp.name
        LIMIT $limit
        """
        
        result = tx.run(query, keyword=keyword, limit=limit)
        procedures = []
        
        for record in result:
            sp = record["sp"]
            procedures.append({
                "id": sp.id,
                "name": sp["name"],
                "schema": sp.get("schema", ""),
                "complexity": sp.get("complexity", 0),
                "last_modified": sp.get("last_modified", ""),
                "description": sp.get("description", "")
            })
        
        return procedures
    
    def get_impact_analysis(self, sp_name: str, max_depth: int = 5) -> Dict[str, Any]:
        """获取存储过程影响分析
        
        Args:
            sp_name: 存储过程名称
            max_depth: 最大分析深度
            
        Returns:
            影响分析信息
        """
        with self.driver.session() as session:
            result = session.read_transaction(self._get_impact_analysis_tx, sp_name, max_depth)
            return result
    
    def _get_impact_analysis_tx(self, tx, sp_name: str, max_depth: int) -> Dict[str, Any]:
        """获取影响分析的事务函数"""
        # 检查存储过程是否存在
        check_query = "MATCH (sp:SP_Node {name: $sp_name}) RETURN sp"
        check_result = tx.run(check_query, sp_name=sp_name).single()
        
        if not check_result:
            return {"error": f"存储过程 {sp_name} 不存在"}
        
        # 获取影响分析数据
        query = """
        MATCH (start:SP_Node {name: $sp_name})
        CALL apoc.path.expandConfig(start, {
            relationshipFilter: "CALLS|REFERENCES",
            minLevel: 1,
            maxLevel: $max_depth
        })
        YIELD path
        WITH DISTINCT last(nodes(path)) AS affected_node
        RETURN 
            count(affected_node) AS total_affected,
            sum(CASE WHEN 'SP_Node' IN labels(affected_node) THEN 1 ELSE 0 END) AS affected_sps,
            sum(CASE WHEN 'Table_Node' IN labels(affected_node) THEN 1 ELSE 0 END) AS affected_tables,
            collect(affected_node) as affected_nodes
        """
        
        result = tx.run(query, sp_name=sp_name, max_depth=max_depth)
        record = result.single()
        
        if not record:
            return {
                "sp_name": sp_name,
                "total_affected": 0,
                "affected_sps": 0,
                "affected_tables": 0,
                "affected_nodes": []
            }
        
        # 处理受影响的节点
        affected_nodes = []
        for node in record["affected_nodes"]:
            node_type = "SP" if "SP_Node" in node.labels else "TABLE"
            affected_nodes.append({
                "id": str(node.id),
                "name": node.get("name", ""),
                "schema": node.get("schema", ""),
                "type": node_type,
                "is_core": node.get("is_core", False) if node_type == "TABLE" else None,
                "complexity": node.get("complexity", 0) if node_type == "SP" else None
            })
        
        return {
            "sp_name": sp_name,
            "total_affected": record["total_affected"],
            "affected_sps": record["affected_sps"],
            "affected_tables": record["affected_tables"],
            "affected_nodes": affected_nodes
        }