#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图谱构建模块

该模块实现了Oracle存储过程调用链图谱的构建功能，将解析结果转换为Neo4j图数据库中的节点和关系。
"""

import os
import json
from typing import Dict, List, Any, Optional, Tuple
from neo4j import GraphDatabase


class GraphBuilder:
    """图谱构建器类"""
    
    def __init__(self, uri: str, username: str, password: str):
        """初始化图谱构建器
        
        Args:
            uri: Neo4j数据库URI
            username: 数据库用户名
            password: 数据库密码
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
    
    def close(self) -> None:
        """关闭数据库连接"""
        self.driver.close()
    
    def create_sp_node(self, sp_info: Dict[str, Any]) -> str:
        """创建存储过程节点
        
        Args:
            sp_info: 存储过程信息
            
        Returns:
            创建的节点ID
        """
        with self.driver.session() as session:
            result = session.write_transaction(self._create_sp_node_tx, sp_info)
            return result
    
    def _create_sp_node_tx(self, tx, sp_info: Dict[str, Any]) -> str:
        """创建存储过程节点的事务函数"""
        query = """
        MERGE (sp:SP_Node {name: $name, schema: $schema})
        ON CREATE SET 
            sp.created = timestamp(),
            sp.complexity = $complexity,
            sp.last_modified = $last_modified,
            sp.description = $description
        ON MATCH SET 
            sp.complexity = $complexity,
            sp.last_modified = $last_modified,
            sp.updated = timestamp()
        RETURN id(sp) AS node_id
        """
        
        params = {
            "name": sp_info.get("name", ""),
            "schema": sp_info.get("schema", ""),
            "complexity": sp_info.get("complexity", 0),
            "last_modified": sp_info.get("last_modified", ""),
            "description": sp_info.get("description", "")
        }
        
        result = tx.run(query, **params)
        record = result.single()
        return record["node_id"] if record else None
    
    def create_table_node(self, table_info: Dict[str, Any]) -> str:
        """创建表节点
        
        Args:
            table_info: 表信息
            
        Returns:
            创建的节点ID
        """
        with self.driver.session() as session:
            result = session.write_transaction(self._create_table_node_tx, table_info)
            return result
    
    def _create_table_node_tx(self, tx, table_info: Dict[str, Any]) -> str:
        """创建表节点的事务函数"""
        query = """
        MERGE (table:Table_Node {name: $name, schema: $schema})
        ON CREATE SET 
            table.created = timestamp(),
            table.is_core = $is_core,
            table.description = $description
        ON MATCH SET 
            table.is_core = $is_core,
            table.updated = timestamp()
        RETURN id(table) AS node_id
        """
        
        params = {
            "name": table_info.get("name", ""),
            "schema": table_info.get("schema", ""),
            "is_core": table_info.get("is_core", False),
            "description": table_info.get("description", "")
        }
        
        result = tx.run(query, **params)
        record = result.single()
        return record["node_id"] if record else None
    
    def create_dynamic_table_node(self, dyn_table_info: Dict[str, Any]) -> str:
        """创建动态表节点
        
        Args:
            dyn_table_info: 动态表信息
            
        Returns:
            创建的节点ID
        """
        with self.driver.session() as session:
            result = session.write_transaction(self._create_dyn_table_node_tx, dyn_table_info)
            return result
    
    def _create_dyn_table_node_tx(self, tx, dyn_table_info: Dict[str, Any]) -> str:
        """创建动态表节点的事务函数"""
        query = """
        MERGE (table:DYN_Table_Node {pattern: $pattern})
        ON CREATE SET 
            table.created = timestamp(),
            table.variables = $variables,
            table.confidence = $confidence,
            table.description = $description
        ON MATCH SET 
            table.variables = $variables,
            table.confidence = $confidence,
            table.updated = timestamp()
        RETURN id(table) AS node_id
        """
        
        params = {
            "pattern": dyn_table_info.get("pattern", ""),
            "variables": json.dumps(dyn_table_info.get("variables", [])),
            "confidence": dyn_table_info.get("confidence", 0.0),
            "description": dyn_table_info.get("description", "")
        }
        
        result = tx.run(query, **params)
        record = result.single()
        return record["node_id"] if record else None
    
    def create_calls_relationship(self, caller_id: str, callee_id: str, rel_info: Dict[str, Any]) -> None:
        """创建调用关系
        
        Args:
            caller_id: 调用者节点ID
            callee_id: 被调用者节点ID
            rel_info: 关系信息
        """
        with self.driver.session() as session:
            session.write_transaction(
                self._create_calls_relationship_tx, 
                caller_id, 
                callee_id, 
                rel_info
            )
    
    def _create_calls_relationship_tx(self, tx, caller_id: str, callee_id: str, rel_info: Dict[str, Any]) -> None:
        """创建调用关系的事务函数"""
        query = """
        MATCH (caller), (callee)
        WHERE id(caller) = $caller_id AND id(callee) = $callee_id
        MERGE (caller)-[r:CALLS]->(callee)
        ON CREATE SET 
            r.created = timestamp(),
            r.depth = $depth,
            r.frequency = $frequency,
            r.is_conditional = $is_conditional,
            r.confidence = $confidence
        ON MATCH SET 
            r.frequency = r.frequency + $frequency,
            r.confidence = $confidence,
            r.updated = timestamp()
        """
        
        params = {
            "caller_id": caller_id,
            "callee_id": callee_id,
            "depth": rel_info.get("depth", 1),
            "frequency": rel_info.get("frequency", 1),
            "is_conditional": rel_info.get("is_conditional", False),
            "confidence": rel_info.get("confidence", 1.0)
        }
        
        tx.run(query, **params)
    
    def create_references_relationship(self, sp_id: str, table_id: str, rel_info: Dict[str, Any]) -> None:
        """创建引用关系
        
        Args:
            sp_id: 存储过程节点ID
            table_id: 表节点ID
            rel_info: 关系信息
        """
        with self.driver.session() as session:
            session.write_transaction(
                self._create_references_relationship_tx, 
                sp_id, 
                table_id, 
                rel_info
            )
    
    def _create_references_relationship_tx(self, tx, sp_id: str, table_id: str, rel_info: Dict[str, Any]) -> None:
        """创建引用关系的事务函数"""
        query = """
        MATCH (sp), (table)
        WHERE id(sp) = $sp_id AND id(table) = $table_id
        MERGE (sp)-[r:REFERENCES]->(table)
        ON CREATE SET 
            r.created = timestamp(),
            r.operation = $operation,
            r.is_dynamic = $is_dynamic,
            r.confidence = $confidence,
            r.last_verified = $last_verified
        ON MATCH SET 
            r.operation = $operation,
            r.confidence = $confidence,
            r.last_verified = $last_verified,
            r.updated = timestamp()
        """
        
        params = {
            "sp_id": sp_id,
            "table_id": table_id,
            "operation": rel_info.get("operation", "SELECT"),
            "is_dynamic": rel_info.get("is_dynamic", False),
            "confidence": rel_info.get("confidence", 1.0),
            "last_verified": rel_info.get("last_verified", "")
        }
        
        tx.run(query, **params)
    
    def create_dyn_references_relationship(self, sp_id: str, dyn_table_id: str, rel_info: Dict[str, Any]) -> None:
        """创建动态引用关系
        
        Args:
            sp_id: 存储过程节点ID
            dyn_table_id: 动态表节点ID
            rel_info: 关系信息
        """
        with self.driver.session() as session:
            session.write_transaction(
                self._create_dyn_references_relationship_tx, 
                sp_id, 
                dyn_table_id, 
                rel_info
            )
    
    def _create_dyn_references_relationship_tx(self, tx, sp_id: str, dyn_table_id: str, rel_info: Dict[str, Any]) -> None:
        """创建动态引用关系的事务函数"""
        query = """
        MATCH (sp), (dyn_table)
        WHERE id(sp) = $sp_id AND id(dyn_table) = $dyn_table_id
        MERGE (sp)-[r:DYN_REFERENCES]->(dyn_table)
        ON CREATE SET 
            r.created = timestamp(),
            r.operation = $operation,
            r.pattern = $pattern,
            r.variables = $variables,
            r.confidence = $confidence,
            r.need_verify = $need_verify
        ON MATCH SET 
            r.operation = $operation,
            r.confidence = $confidence,
            r.need_verify = $need_verify,
            r.updated = timestamp()
        """
        
        params = {
            "sp_id": sp_id,
            "dyn_table_id": dyn_table_id,
            "operation": rel_info.get("operation", "SELECT"),
            "pattern": rel_info.get("pattern", ""),
            "variables": json.dumps(rel_info.get("variables", [])),
            "confidence": rel_info.get("confidence", 0.7),
            "need_verify": rel_info.get("need_verify", True)
        }
        
        tx.run(query, **params)
    
    def get_call_chain(self, sp_name: str, max_depth: int = 3) -> Dict[str, Any]:
        """获取存储过程调用链
        
        Args:
            sp_name: 存储过程名称
            max_depth: 最大调用深度
            
        Returns:
            调用链信息
        """
        with self.driver.session() as session:
            result = session.read_transaction(self._get_call_chain_tx, sp_name, max_depth)
            return result
    
    def _get_call_chain_tx(self, tx, sp_name: str, max_depth: int) -> Dict[str, Any]:
        """获取调用链的事务函数"""
        query = """
        MATCH path = (start:SP_Node {name: $sp_name})-[:CALLS*1..%d]->(sp:SP_Node)
        OPTIONAL MATCH (sp)-[ref:REFERENCES]->(table:Table_Node)
        RETURN path, sp, ref, table
        """ % max_depth
        
        result = tx.run(query, sp_name=sp_name)
        
        # 处理结果为JSON格式
        nodes = {}
        relationships = []
        
        for record in result:
            path = record["path"]
            sp = record["sp"]
            ref = record["ref"]
            table = record["table"]
            
            # 添加路径中的所有节点
            for node in path.nodes:
                if node.id not in nodes:
                    nodes[node.id] = {
                        "id": node.id,
                        "labels": list(node.labels),
                        "properties": dict(node)
                    }
            
            # 添加路径中的所有关系
            for rel in path.relationships:
                relationships.append({
                    "id": rel.id,
                    "type": rel.type,
                    "start": rel.start_node.id,
                    "end": rel.end_node.id,
                    "properties": dict(rel)
                })
            
            # 添加表节点和引用关系
            if table is not None:
                if table.id not in nodes:
                    nodes[table.id] = {
                        "id": table.id,
                        "labels": list(table.labels),
                        "properties": dict(table)
                    }
                
                if ref is not None:
                    relationships.append({
                        "id": ref.id,
                        "type": ref.type,
                        "start": ref.start_node.id,
                        "end": ref.end_node.id,
                        "properties": dict(ref)
                    })
        
        return {
            "nodes": list(nodes.values()),
            "relationships": relationships
        }
    
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
                "total_affected": 0,
                "affected_sps": 0,
                "affected_tables": 0,
                "affected_nodes": []
            }
        
        # 处理受影响的节点
        affected_nodes = []
        for node in record["affected_nodes"]:
            affected_nodes.append({
                "id": node.id,
                "labels": list(node.labels),
                "properties": dict(node)
            })
        
        return {
            "total_affected": record["total_affected"],
            "affected_sps": record["affected_sps"],
            "affected_tables": record["affected_tables"],
            "affected_nodes": affected_nodes
        }