#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
动态SQL解析器

该模块实现了动态SQL解析器，用于解析Oracle存储过程中的动态表名和变量引用。
"""

import re
from typing import Dict, List, Any, Optional


class DynamicSQLParser:
    """动态SQL解析器类"""
    
    def __init__(self, ner_model=None):
        """初始化动态SQL解析器
        
        Args:
            ner_model: NER模型实例，如果为None则仅使用正则表达式解析
        """
        self.ner_model = ner_model
        # 变量模式：||VAR_NAME或:VAR_NAME
        self.var_pattern = re.compile(r"\|{2}\s*([A-Z0-9_]+)|:([A-Z0-9_]+)")
        # 动态表名模式
        self.table_pattern = re.compile(r"FROM\s+([A-Za-z0-9_$]+(?:_\|{2}[A-Z0-9_]+\|{2}[A-Za-z0-9_$]+|_:[A-Z0-9_]+))")
    
    def extract_dynamic_tables(self, sql_text: str) -> List[Dict[str, Any]]:
        """提取动态表引用
        
        Args:
            sql_text: SQL文本
            
        Returns:
            动态表列表，每个表包含模式、变量和置信度
        """
        dynamic_tables = []
        
        # 使用NER模型识别动态表引用（如果可用）
        if self.ner_model:
            entities = self.ner_model.predict(sql_text)
            ner_tables = [e for e in entities if e["entity"] == "DYN_TABLE"]
            for table in ner_tables:
                table_pattern = table["value"]
                variables = self.var_pattern.findall(table_pattern)
                # 合并两种捕获组的结果
                var_names = [var[0] if var[0] else var[1] for var in variables]
                dynamic_tables.append({
                    "pattern": table_pattern,
                    "variables": var_names,
                    "confidence": table.get("confidence", 0.7),  # 动态表默认置信度
                    "source": "ner"
                })
        
        # 使用正则表达式识别动态表引用
        regex_tables = self.table_pattern.findall(sql_text)
        for table_pattern in regex_tables:
            # 检查是否已经由NER模型识别
            if any(t["pattern"] == table_pattern for t in dynamic_tables):
                continue
                
            variables = self.var_pattern.findall(table_pattern)
            # 合并两种捕获组的结果
            var_names = [var[0] if var[0] else var[1] for var in variables]
            dynamic_tables.append({
                "pattern": table_pattern,
                "variables": var_names,
                "confidence": 0.6,  # 正则表达式识别的置信度略低
                "source": "regex"
            })
        
        return dynamic_tables
    
    def resolve_with_runtime_logs(self, dynamic_table: Dict[str, Any], runtime_logs: Dict[str, str]) -> Dict[str, Any]:
        """结合运行时日志解析实际表名
        
        Args:
            dynamic_table: 动态表信息
            runtime_logs: 运行时日志，变量名到值的映射
            
        Returns:
            更新后的动态表信息，包含解析后的实际表名
        """
        table_pattern = dynamic_table["pattern"]
        resolved_pattern = table_pattern
        
        # 替换所有变量
        for var in dynamic_table["variables"]:
            if var in runtime_logs:
                # 替换变量为实际值
                actual_value = runtime_logs[var]
                resolved_pattern = resolved_pattern.replace(f"||{var}", actual_value)
                resolved_pattern = resolved_pattern.replace(f":{var}", actual_value)
        
        # 更新动态表信息
        dynamic_table["resolved_name"] = resolved_pattern
        dynamic_table["confidence"] = 0.9  # 提高置信度
        
        return dynamic_table
    
    def extract_variables(self, sql_text: str) -> List[str]:
        """提取SQL中的所有变量
        
        Args:
            sql_text: SQL文本
            
        Returns:
            变量名列表
        """
        variables = self.var_pattern.findall(sql_text)
        # 合并两种捕获组的结果并去重
        var_names = list(set([var[0] if var[0] else var[1] for var in variables]))
        return var_names