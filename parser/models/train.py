#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
DeepSeek-NER模型训练器

该模块实现了DeepSeek-NER模型的训练功能。
"""

import os
import json
from typing import Dict, List, Any, Optional, Union
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer, AutoModelForTokenClassification,
    Trainer, TrainingArguments, DataCollatorForTokenClassification
)
from datasets import Dataset as HFDataset, load_dataset
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from .config import ModelConfig


class NERDataset(Dataset):
    """NER数据集类"""
    
    def __init__(self, texts, tags, tokenizer, label2id):
        """初始化数据集
        
        Args:
            texts: 文本列表
            tags: 标签列表
            tokenizer: 分词器
            label2id: 标签到ID的映射
        """
        self.texts = texts
        self.tags = tags
        self.tokenizer = tokenizer
        self.label2id = label2id
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        # 对文本进行分词
        tokenized = self.tokenizer(
            self.texts[idx],
            padding="max_length",
            truncation=True,
            return_offsets_mapping=True,
            return_tensors="pt"
        )
        
        # 处理标签
        labels = torch.ones(len(tokenized["input_ids"]), dtype=torch.long) * -100  # 忽略的标签为-100
        
        token_idx = 0
        for tag in self.tags[idx]:
            # 将标签映射到token
            if token_idx < len(tokenized["input_ids"]):
                labels[token_idx] = self.label2id.get(tag, 0)  # 默认为"O"标签
            token_idx += 1
        
        return {
            "input_ids": tokenized["input_ids"].squeeze(),
            "attention_mask": tokenized["attention_mask"].squeeze(),
            "labels": labels.squeeze()
        }


class DeepSeekNERTrainer:
    """DeepSeek-NER模型训练器类"""
    
    def __init__(self, config: Optional[ModelConfig] = None):
        """初始化训练器
        
        Args:
            config: 模型配置，如果为None则使用默认配置
        """
        self.config = config or ModelConfig()
        self.device = torch.device(self.config.device if torch.cuda.is_available() else "cpu")
        self.tokenizer = None
        self.model = None
    
    def load_data(self, data_path: str) -> Dict[str, HFDataset]:
        """加载数据集
        
        Args:
            data_path: 数据路径，可以是JSON文件或Hugging Face数据集名称
            
        Returns:
            数据集字典，包含训练集、验证集和测试集
        """
        if os.path.exists(data_path):
            # 加载本地JSON文件
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 转换为Hugging Face数据集格式
            train_data = {"text": [], "tags": []}
            val_data = {"text": [], "tags": []}
            test_data = {"text": [], "tags": []}
            
            # 根据数据划分比例分配数据
            train_ratio = 0.8
            val_ratio = 0.1
            n_samples = len(data)
            n_train = int(n_samples * train_ratio)
            n_val = int(n_samples * val_ratio)
            
            for i, item in enumerate(data):
                if i < n_train:
                    train_data["text"].append(item["text"])
                    train_data["tags"].append(item["tags"])
                elif i < n_train + n_val:
                    val_data["text"].append(item["text"])
                    val_data["tags"].append(item["tags"])
                else:
                    test_data["text"].append(item["text"])
                    test_data["tags"].append(item["tags"])
            
            train_dataset = HFDataset.from_dict(train_data)
            val_dataset = HFDataset.from_dict(val_data)
            test_dataset = HFDataset.from_dict(test_data)
        else:
            # 尝试从Hugging Face加载数据集
            try:
                dataset = load_dataset(data_path)
                train_dataset = dataset["train"]
                val_dataset = dataset["validation"] if "validation" in dataset else None
                test_dataset = dataset["test"] if "test" in dataset else None
                
                # 如果没有验证集，从训练集中分割
                if val_dataset is None:
                    splits = train_dataset.train_test_split(test_size=0.1)
                    train_dataset = splits["train"]
                    val_dataset = splits["test"]
                
                # 如果没有测试集，从验证集中分割
                if test_dataset is None:
                    splits = val_dataset.train_test_split(test_size=0.5)
                    val_dataset = splits["train"]
                    test_dataset = splits["test"]
            except Exception as e:
                raise ValueError(f"无法加载数据集 {data_path}: {str(e)}")
        
        return {
            "train": train_dataset,
            "validation": val_dataset,
            "test": test_dataset
        }
    
    def preprocess_data(self, datasets: Dict[str, HFDataset]) -> Dict[str, HFDataset]:
        """预处理数据集
        
        Args:
            datasets: 数据集字典
            
        Returns:
            预处理后的数据集字典
        """
        # 加载分词器
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_path or self.config.model_name
        )
        
        def tokenize_and_align_labels(examples):
            tokenized_inputs = self.tokenizer(
                examples["text"],
                padding="max_length",
                truncation=True,
                max_length=self.config.max_length,
                return_tensors="pt"
            )
            
            labels = []
            for i, tags in enumerate(examples["tags"]):
                label = []
                for j, tag in enumerate(tags):
                    label.append(self.config.get_label2id().get(tag, 0))  # 默认为"O"标签
                
                # 填充到最大长度
                if len(label) < self.config.max_length:
                    label.extend([-100] * (self.config.max_length - len(label)))
                else:
                    label = label[:self.config.max_length]
                
                labels.append(label)
            
            tokenized_inputs["labels"] = labels
            return tokenized_inputs
        
        # 应用预处理
        processed_datasets = {}
        for split, dataset in datasets.items():
            processed_datasets[split] = dataset.map(
                tokenize_and_align_labels,
                batched=True,
                remove_columns=dataset.column_names
            )
        
        return processed_datasets
    
    def train(self, datasets: Dict[str, HFDataset], output_dir: str) -> None:
        """训练模型
        
        Args:
            datasets: 预处理后的数据集字典
            output_dir: 模型输出目录
        """
        # 加载预训练模型
        self.model = AutoModelForTokenClassification.from_pretrained(
            self.config.model_path or self.config.model_name,
            num_labels=len(self.config.entity_types),
            id2label=self.config.get_id2label(),
            label2id=self.config.get_label2id()
        )
        
        # 定义评估函数
        def compute_metrics(p):
            predictions, labels = p
            predictions = np.argmax(predictions, axis=2)
            
            # 只考虑非填充标记
            true_predictions = [
                [self.config.get_id2label()[p] for (p, l) in zip(prediction, label) if l != -100]
                for prediction, label in zip(predictions, labels)
            ]
            true_labels = [
                [self.config.get_id2label()[l] for (p, l) in zip(prediction, label) if l != -100]
                for prediction, label in zip(predictions, labels)
            ]
            
            # 平坦化列表
            true_predictions_flat = [p for sublist in true_predictions for p in sublist]
            true_labels_flat = [l for sublist in true_labels for l in sublist]
            
            # 计算指标
            accuracy = accuracy_score(true_labels_flat, true_predictions_flat)
            precision, recall, f1, _ = precision_recall_fscore_support(
                true_labels_flat,
                true_predictions_flat,
                average="weighted"
            )
            
            return {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1
            }
        
        # 设置训练参数
        training_args = TrainingArguments(
            output_dir=output_dir,
            evaluation_strategy="epoch",
            learning_rate=5e-5,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            num_train_epochs=3,
            weight_decay=0.01,
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="f1",
            save_total_limit=2,
            report_to="tensorboard"
        )
        
        # 创建数据整理器
        data_collator = DataCollatorForTokenClassification(
            self.tokenizer,
            pad_to_multiple_of=8 if self.config.device == "cuda" else None
        )
        
        # 创建训练器
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=datasets["train"],
            eval_dataset=datasets["validation"],
            tokenizer=self.tokenizer,
            data_collator=data_collator,
            compute_metrics=compute_metrics
        )
        
        # 开始训练
        trainer.train()
        
        # 保存最终模型
        self.model.save_pretrained(os.path.join(output_dir, "final_model"))
        self.tokenizer.save_pretrained(os.path.join(output_dir, "final_model"))
        
        # 评估模型
        eval_results = trainer.evaluate(datasets["test"])
        print(f"测试集评估结果: {eval_results}")
        
        # 保存评估结果
        with open(os.path.join(output_dir, "eval_results.json"), "w", encoding="utf-8") as f:
            json.dump(eval_results, f, indent=2, ensure_ascii=False)
    
    def export_onnx(self, output_path: str) -> None:
        """导出ONNX模型
        
        Args:
            output_path: ONNX模型输出路径
        """
        if self.model is None:
            raise ValueError("模型未加载，请先训练模型或加载已有模型")
        
        # 创建样本输入
        dummy_input = {
            "input_ids": torch.ones((1, self.config.max_length), dtype=torch.long).to(self.device),
            "attention_mask": torch.ones((1, self.config.max_length), dtype=torch.long).to(self.device)
        }
        
        # 设置动态轴
        dynamic_axes = {
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "output": {0: "batch_size", 1: "sequence_length"}
        }
        
        # 导出ONNX模型
        torch.onnx.export(
            self.model,
            (dummy_input["input_ids"], dummy_input["attention_mask"]),
            output_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["output"],
            dynamic_axes=dynamic_axes,
            opset_version=12
        )
        
        print(f"ONNX模型已导出至: {output_path}")


def main():
    """命令行入口函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DeepSeek-NER模型训练器")
    parser.add_argument("--data", required=True, help="数据集路径或名称")
    parser.add_argument("--output", required=True, help="模型输出目录")
    parser.add_argument("--model", default=None, help="预训练模型路径或名称")
    parser.add_argument("--batch-size", type=int, default=8, help="批次大小")
    parser.add_argument("--max-length", type=int, default=512, help="最大序列长度")
    parser.add_argument("--export-onnx", help="导出ONNX模型的路径")
    
    args = parser.parse_args()
    
    # 创建模型配置
    config = ModelConfig()
    if args.model:
        config.model_path = args.model
    config.batch_size = args.batch_size
    config.max_length = args.max_length
    
    # 创建训练器
    trainer = DeepSeekNERTrainer(config)
    
    # 加载数据
    datasets = trainer.load_data(args.data)
    
    # 预处理数据
    processed_datasets = trainer.preprocess_data(datasets)
    
    # 训练模型
    trainer.train(processed_datasets, args.output)
    
    # 导出ONNX模型
    if args.export_onnx:
        trainer.export_onnx(args.export_onnx)


if __name__ == "__main__":
    main()