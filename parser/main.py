#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Oracle存储过程解析器主程序

该模块负责解析Oracle存储过程代码，提取依赖关系，并构建调用链图谱。
"""

import os
import sys
import argparse
from typing import List, Dict, Any, Optional

# 导入自定义模块
try:
    from parser.models.config import ModelConfig
    from parser.utils.dynamic_sql import DynamicSQLParser
    from parser.utils.synonym import SynonymResolver
except ImportError:
    # 处理相对导入
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from parser.models.config import ModelConfig
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
        self.dynamic_sql_parser = DynamicSQLParser()
        self.synonym_resolver = SynonymResolver()
        
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
        # TODO: 实现NER模型调用逻辑
        # 目前返回一个占位结果
        result = {
            "source": source_name,
            "procedure_name": "<placeholder>",
            "dependencies": {
                "procedures": [],  # 调用的其他存储过程
                "tables": [],      # 访问的表
                "dynamic_tables": []  # 动态访问的表
            },
            "confidence": 0.0  # 解析结果的置信度
        }
        
        return result
    
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
                if file.endswith(('.sql', '.pls', '.plb')):
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
    
    args = parser.parse_args()
    
    sp_parser = OracleStoredProcedureParser()
    
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