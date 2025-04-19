#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Oracle存储过程解析器主程序

该模块负责解析Oracle存储过程代码，提取依赖关系，并构建调用链图谱。
"""

import os
import sys
import argparse
import re
from typing import List, Dict, Any, Optional

# 导入自定义模块
try:
    from parser.models.config import ModelConfig
    from parser.models.ner_model import DeepSeekNER
    from parser.utils.dynamic_sql import DynamicSQLParser
    from parser.utils.synonym import SynonymResolver
except ImportError:
    # 处理相对导入
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from parser.models.config import ModelConfig
    from parser.models.ner_model import DeepSeekNER
    from parser.utils.dynamic_sql import DynamicSQLParser
    from parser.utils.synonym import SynonymResolver


class OracleStoredProcedureParser:
    """Oracle存储过程解析器类"""
    
    def __init__(self, model_config: Optional[ModelConfig] = None):
        """初始化解析器
        
        Args:
            model_config: NER模型配置，如果为None则使用默认配置
        """
        self.model_config = model_config or ModelConfig()
        # 加载NER模型（如果可用）
        try:
            self.ner_model = DeepSeekNER(self.model_config)
            self.use_ner = True
            print("NER模型已加载，使用DeepSeek-NER进行解析")
        except Exception as e:
            self.ner_model = None
            self.use_ner = False
            print(f"NER模型加载失败: {str(e)}，使用正则表达式进行解析")
        
        # 初始化解析工具
        self.dynamic_sql_parser = DynamicSQLParser(self.ner_model)
        self.synonym_resolver = SynonymResolver()
        
        # 初始化正则表达式（作为备用）
        self.sp_name_re = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+(\w+)", re.IGNORECASE)
        self.sp_call_re = re.compile(r"CALL\s+(\w+)\(|EXECUTE\s+(\w+)|BEGIN\s+(\w+)\(", re.IGNORECASE)
        self.static_table_re = re.compile(r"FROM\s+(\w+(?:\.\w+)?)", re.IGNORECASE)
        
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """解析单个存储过程文件
        
        Args:
            file_path: 存储过程文件路径
            
        Returns:
            包含解析结果的字典
        """
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return self.parse_content(content, file_path)
    
    def parse_content(self, content: str, source_name: str = "<unknown>") -> Dict[str, Any]:
        """解析存储过程内容
        
        Args:
            content: 存储过程代码内容
            source_name: 源文件名或标识符
            
        Returns:
            包含解析结果的字典
        """
        # 提取存储过程名称
        sp_name = self._extract_procedure_name(content)
        
        # 使用NER模型或正则表达式提取依赖
        if self.use_ner:
            dependencies = self._extract_dependencies_with_ner(content)
            confidence = 0.9  # NER模型提供更高置信度
        else:
            dependencies = self._extract_dependencies_with_regex(content)
            confidence = 0.7  # 正则表达式提供较低置信度
        
        # 返回解析结果
        result = {
            "source": source_name,
            "procedure_name": sp_name,
            "dependencies": dependencies,
            "confidence": confidence
        }
        
        return result
    
    def _extract_procedure_name(self, content: str) -> str:
        """提取存储过程名称
        
        Args:
            content: 存储过程代码内容
            
        Returns:
            存储过程名称
        """
        if self.use_ner:
            entities = self.ner_model.predict(content)
            for entity in entities:
                if entity["entity"] == "SP" and "CREATE" in content[:entity["start"]].upper():
                    return entity["value"]
        
        # 使用正则表达式作为备用
        match = self.sp_name_re.search(content)
        if match:
            return match.group(1)
        
        # 如果无法提取，返回文件名或占位符
        if os.path.basename(self.source):
            return os.path.splitext(os.path.basename(self.source))[0]
        return "<unknown_procedure>"
    
    def _extract_dependencies_with_ner(self, content: str) -> Dict[str, List[Dict[str, Any]]]:
        """使用NER模型提取依赖关系
        
        Args:
            content: 存储过程代码内容
            
        Returns:
            依赖关系字典
        """
        # 使用NER模型提取实体
        entities = self.ner_model.predict(content)
        
        # 分类提取的实体
        procedures = []
        tables = []
        dynamic_tables = []
        
        for entity in entities:
            if entity["entity"] == "SP" and "CREATE" not in content[:entity["start"]].upper():
                # 这是被调用的存储过程，不是当前正在定义的存储过程
                procedures.append({
                    "name": entity["value"],
                    "confidence": entity["confidence"],
                    "line": content[:entity["start"]].count('\n') + 1
                })
            elif entity["entity"] == "TABLE":
                # 静态表引用
                resolved = self.synonym_resolver.resolve_synonym(entity["value"])
                tables.append({
                    "name": resolved["resolved"],
                    "original": entity["value"],
                    "is_synonym": resolved["is_synonym"],
                    "confidence": entity["confidence"] * resolved["confidence"],
                    "line": content[:entity["start"]].count('\n') + 1
                })
            elif entity["entity"] == "DYN_TABLE":
                # 动态表引用
                dynamic_tables.append({
                    "pattern": entity["value"],
                    "variables": self.dynamic_sql_parser.extract_variables(entity["value"]),
                    "confidence": entity["confidence"],
                    "line": content[:entity["start"]].count('\n') + 1
                })
        
        # 使用动态SQL解析器提取更多动态表引用
        more_dynamic_tables = self.dynamic_sql_parser.extract_dynamic_tables(content)
        for table in more_dynamic_tables:
            # 检查是否已经存在
            if not any(dt["pattern"] == table["pattern"] for dt in dynamic_tables):
                dynamic_tables.append(table)
        
        return {
            "procedures": procedures,
            "tables": tables,
            "dynamic_tables": dynamic_tables
        }
    
    def _extract_dependencies_with_regex(self, content: str) -> Dict[str, List[Dict[str, Any]]]:
        """使用正则表达式提取依赖关系
        
        Args:
            content: 存储过程代码内容
            
        Returns:
            依赖关系字典
        """
        # 提取被调用的存储过程
        procedures = []
        for match in self.sp_call_re.finditer(content):
            sp_name = match.group(1) or match.group(2) or match.group(3)
            if sp_name:
                procedures.append({
                    "name": sp_name,
                    "confidence": 0.7,
                    "line": content[:match.start()].count('\n') + 1
                })
        
        # 提取静态表引用
        tables = []
        for match in self.static_table_re.finditer(content):
            table_name = match.group(1)
            resolved = self.synonym_resolver.resolve_synonym(table_name)
            tables.append({
                "name": resolved["resolved"],
                "original": table_name,
                "is_synonym": resolved["is_synonym"],
                "confidence": 0.7 * resolved["confidence"],
                "line": content[:match.start()].count('\n') + 1
            })
        
        # 提取动态表引用
        dynamic_tables = self.dynamic_sql_parser.extract_dynamic_tables(content)
        
        return {
            "procedures": procedures,
            "tables": tables,
            "dynamic_tables": dynamic_tables
        }
    
    def batch_parse(self, directory: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """批量解析目录中的存储过程文件
        
        Args:
            directory: 存储过程文件目录
            recursive: 是否递归解析子目录
            
        Returns:
            包含所有解析结果的列表
        """
        results = []
        
        # 遍历目录中的文件
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(('.sql', '.pls', '.plb', '.bdy')):
                    file_path = os.path.join(root, file)
                    try:
                        result = self.parse_file(file_path)
                        results.append(result)
                    except Exception as e:
                        print(f"Error parsing {file_path}: {e}")
            
            if not recursive:
                break
        
        return results


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="Oracle存储过程解析器")
    parser.add_argument("input", help="输入文件或目录路径")
    parser.add_argument("--recursive", "-r", action="store_true", help="递归解析子目录")
    parser.add_argument("--output", "-o", help="输出结果的JSON文件路径")
    parser.add_argument("--use-ner", action="store_true", help="使用NER模型进行解析")
    
    args = parser.parse_args()
    
    # 创建模型配置
    if args.use_ner:
        model_config = ModelConfig()
    else:
        model_config = None
    
    # 创建解析器
    sp_parser = OracleStoredProcedureParser(model_config)
    
    # 解析输入
    if os.path.isdir(args.input):
        results = sp_parser.batch_parse(args.input, args.recursive)
    else:
        results = [sp_parser.parse_file(args.input)]
    
    # 输出结果
    import json
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()