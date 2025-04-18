#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepSeek-NER模型配置

该模块定义了DeepSeek-NER模型的配置参数和加载方法。
"""

import os
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """DeepSeek-NER模型配置类"""
    
    # 模型基础配置
    model_name: str = "deepseek-ai/deepseek-coder-16b-base"
    model_path: Optional[str] = None  # 本地模型路径，如果为None则从HuggingFace下载
    device: str = "cuda"  # 使用的设备，可选：cuda, cpu
    
    # NER任务配置
    entity_types: List[str] = field(default_factory=lambda: [
        "SP",           # 存储过程
        "TABLE",        # 表
        "DYN_TABLE",    # 动态表
        "FUNCTION",     # 函数
        "PACKAGE",      # 包
        "SCHEMA",       # 模式
        "VARIABLE"      # 变量
    ])
    
    # 推理配置
    batch_size: int = 4
    max_length: int = 512
    confidence_threshold: float = 0.5  # 实体识别置信度阈值
    
    def get_labels(self) -> Dict[int, str]:
        """获取标签映射"""
        return {i: label for i, label in enumerate(self.entity_types)}
    
    def get_id2label(self) -> Dict[int, str]:
        """获取ID到标签的映射"""
        return {i: label for i, label in enumerate(self.entity_types)}
    
    def get_label2id(self) -> Dict[str, int]:
        """获取标签到ID的映射"""
        return {label: i for i, label in enumerate(self.entity_types)}
    
    def to_dict(self) -> Dict[str, Union[str, List[str], int, float]]:
        """将配置转换为字典"""
        return {
            "model_name": self.model_name,
            "model_path": self.model_path,
            "device": self.device,
            "entity_types": self.entity_types,
            "batch_size": self.batch_size,
            "max_length": self.max_length,
            "confidence_threshold": self.confidence_threshold
        }