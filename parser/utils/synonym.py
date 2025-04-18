#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
同义词解析器

该模块实现了同义词解析器，用于解析Oracle存储过程中的表同义词引用。
"""

import re
from typing import Dict, List, Any, Optional, Tuple


class SynonymResolver:
    """同义词解析器类"""
    
    def __init__(self, oracle_connection=None):
        """初始化同义词解析器
        
        Args:
            oracle_connection: Oracle数据库连接，如果为None则使用本地缓存
        """
        self.connection = oracle_connection
        self.synonym_map = {}
        self.cache_file = "synonym_cache.json"
        
        # 如果提供了数据库连接，则加载同义词
        if self.connection:
            self.load_synonyms()
    
    def load_synonyms(self) -> Dict[str, str]:
        """从Oracle数据字典加载同义词映射
        
        Returns:
            同义词映射字典，键为同义词名称，值为实际表名
        """
        if not self.connection:
            return self._load_from_cache()
        
        try:
            query = """SELECT synonym_name, table_owner, table_name 
                      FROM all_synonyms"""
            cursor = self.connection.cursor()
            cursor.execute(query)
            
            for row in cursor:
                synonym_name, owner, table_name = row
                self.synonym_map[synonym_name.upper()] = f"{owner}.{table_name}"
            
            # 缓存同义词映射
            self._save_to_cache()
            
            return self.synonym_map
        except Exception as e:
            print(f"加载同义词映射失败: {str(e)}")
            return self._load_from_cache()
    
    def _load_from_cache(self) -> Dict[str, str]:
        """从本地缓存加载同义词映射"""
        import json
        import os
        
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    self.synonym_map = json.load(f)
                return self.synonym_map
            except Exception as e:
                print(f"从缓存加载同义词映射失败: {str(e)}")
        
        return {}
    
    def _save_to_cache(self) -> None:
        """将同义词映射保存到本地缓存"""
        import json
        
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.synonym_map, f)
        except Exception as e:
            print(f"保存同义词映射到缓存失败: {str(e)}")
    
    def resolve_synonym(self, table_name: str) -> Dict[str, Any]:
        """解析表名的同义词引用
        
        Args:
            table_name: 表名
            
        Returns:
            解析结果，包含原始表名、解析后的表名和置信度
        """
        # 转换为大写以匹配Oracle对象名
        table_upper = table_name.upper()
        
        if table_upper in self.synonym_map:
            return {
                "original": table_name,
                "resolved": self.synonym_map[table_upper],
                "confidence": 1.0,  # 同义词映射确定性为1.0
                "is_synonym": True
            }
        
        # 检查是否包含模式前缀
        parts = table_upper.split(".")
        if len(parts) == 2 and parts[1] in self.synonym_map:
            resolved = self.synonym_map[parts[1]]
            return {
                "original": table_name,
                "resolved": f"{parts[0]}.{resolved}",
                "confidence": 1.0,
                "is_synonym": True
            }
        
        # 不是同义词
        return {
            "original": table_name,
            "resolved": table_name,
            "confidence": 1.0,
            "is_synonym": False
        }
    
    def batch_resolve(self, table_names: List[str]) -> List[Dict[str, Any]]:
        """批量解析表名的同义词引用
        
        Args:
            table_names: 表名列表
            
        Returns:
            解析结果列表
        """
        return [self.resolve_synonym(table) for table in table_names]
    
    def extract_and_resolve_tables(self, sql_text: str) -> List[Dict[str, Any]]:
        """从SQL文本中提取并解析表名
        
        Args:
            sql_text: SQL文本
            
        Returns:
            解析后的表信息列表
        """
        # 简单的表名提取正则表达式
        table_pattern = re.compile(r"FROM\s+([A-Za-z0-9_$.]+)")
        tables = table_pattern.findall(sql_text)
        
        # 解析每个表名
        resolved_tables = []
        for table in tables:
            resolved = self.resolve_synonym(table)
            resolved["source_sql"] = sql_text
            resolved_tables.append(resolved)
        
        return resolved_tables