#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepSeek-NER模型实现

该模块实现了基于DeepSeek-16B的命名实体识别模型，用于解析Oracle存储过程代码。
"""

import os
import torch
from typing import Dict, List, Any, Optional, Union
from transformers import AutoTokenizer, AutoModelForTokenClassification

from .config import ModelConfig


class DeepSeekNER:
    """DeepSeek命名实体识别模型类"""
    
    def __init__(self, config: Optional[ModelConfig] = None):
        """初始化NER模型
        
        Args:
            config: 模型配置，如果为None则使用默认配置
        """
        self.config = config or ModelConfig()
        self.device = torch.device(self.config.device if torch.cuda.is_available() else "cpu")
        self._load_model()
    
    def _load_model(self) -> None:
        """加载预训练模型"""
        model_path = self.config.model_path or self.config.model_name
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForTokenClassification.from_pretrained(
                model_path,
                num_labels=len(self.config.entity_types),
                id2label=self.config.get_id2label(),
                label2id=self.config.get_label2id()
            )
            self.model.to(self.device)
            self.model.eval()  # 设置为评估模式
        except Exception as e:
            raise RuntimeError(f"加载DeepSeek-NER模型失败: {str(e)}")
    
    def predict(self, text: str) -> List[Dict[str, Any]]:
        """预测文本中的实体
        
        Args:
            text: 输入文本
            
        Returns:
            实体列表，每个实体包含类型、起始位置、结束位置、值和置信度
        """
        # 对输入文本进行分词
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, 
                               max_length=self.config.max_length)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # 执行预测
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1)
        
        # 解码预测结果
        predictions = torch.argmax(logits, dim=-1)[0].cpu().numpy()
        confidence_scores = torch.max(probabilities, dim=-1)[0][0].cpu().numpy()
        
        # 提取实体
        entities = []
        current_entity = None
        
        for i, (pred, conf) in enumerate(zip(predictions, confidence_scores)):
            token_id = inputs["input_ids"][0][i].item()
            token = self.tokenizer.convert_ids_to_tokens(token_id)
            
            # 跳过特殊token
            if token in [self.tokenizer.cls_token, self.tokenizer.sep_token, self.tokenizer.pad_token]:
                continue
            
            # 获取实体类型
            entity_type = self.config.get_labels().get(pred, "O")
            
            # 如果不是实体，结束当前实体
            if entity_type == "O" or conf < self.config.confidence_threshold:
                if current_entity:
                    entities.append(current_entity)
                    current_entity = None
                continue
            
            # 获取token在原始文本中的位置
            token_start = text.find(token, current_entity["end"] if current_entity else 0)
            token_end = token_start + len(token)
            
            # 如果是新实体或不同类型的实体，创建新实体
            if not current_entity or current_entity["entity"] != entity_type:
                if current_entity:
                    entities.append(current_entity)
                
                current_entity = {
                    "entity": entity_type,
                    "start": token_start,
                    "end": token_end,
                    "value": token,
                    "confidence": float(conf)
                }
            else:
                # 扩展当前实体
                current_entity["end"] = token_end
                current_entity["value"] = text[current_entity["start"]:token_end]
                current_entity["confidence"] = (current_entity["confidence"] + float(conf)) / 2
        
        # 添加最后一个实体
        if current_entity:
            entities.append(current_entity)
        
        return entities
    
    def batch_predict(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """批量预测文本中的实体
        
        Args:
            texts: 输入文本列表
            
        Returns:
            每个文本的实体列表
        """
        results = []
        for i in range(0, len(texts), self.config.batch_size):
            batch = texts[i:i + self.config.batch_size]
            batch_results = [self.predict(text) for text in batch]
            results.extend(batch_results)
        return results