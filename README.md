# Oracle存储过程3D调用链分析图谱系统

## 项目概述

本项目是一个用于分析Oracle存储过程调用关系的3D可视化系统，能够自动解析存储过程代码，构建调用链图谱，并通过3D界面直观展示存储过程之间的调用关系和数据表依赖。

## 系统架构

系统采用分层架构，包含五个核心模块：

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  解析器模块     │────▶│  图谱构建模块   │────▶│  API接口模块    │
│ (DeepSeek-NER)  │     │   (Neo4j)       │     │   (FastAPI)     │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                         ┌─────────────────┐     ┌─────────────────┐
                         │ 部署监控模块    │◀────│ 3D可视化模块    │
                         │ (Docker+ELK)    │     │  (Three.js)     │
                         └─────────────────┘     └─────────────────┘
```

## 技术栈

- **解析器模块**: Python + DeepSeek-16B + NER
- **图谱构建模块**: Neo4j 5.0+
- **API接口模块**: FastAPI + Uvicorn
- **3D可视化模块**: Three.js + Vue3
- **部署监控模块**: Docker + Kubernetes + ELK

## 目录结构

```
/
├── parser/                # 解析器模块
│   ├── models/           # NER模型
│   ├── utils/            # 工具函数
│   └── main.py           # 主程序
├── graph/                # 图谱构建模块
│   ├── models/           # 数据模型
│   └── queries/          # 查询语句
├── api/                  # API接口模块
│   ├── models/           # 数据模型
│   ├── routers/          # 路由
│   └── main.py           # 主程序
├── frontend/            # 前端可视化模块
│   ├── src/              # 源代码
│   ├── public/           # 静态资源
│   └── package.json      # 依赖配置
├── deploy/              # 部署配置
│   ├── docker/           # Docker配置
│   └── k8s/              # Kubernetes配置
└── tests/               # 测试用例
```

## 快速开始

### 环境要求

- Python 3.8+
- Node.js 14+
- Docker & Docker Compose
- Neo4j 5.0+

### 安装与运行

1. 克隆仓库
```bash
git clone https://github.com/your-org/oracle-plus.git
cd oracle-plus
```

2. 使用Docker Compose启动所有服务
```bash
docker-compose up -d
```

3. 访问Web界面
```
http://localhost:3000
```

## 功能特性

- 自动解析Oracle存储过程代码，识别调用关系和表依赖
- 支持动态SQL解析，处理运行时生成的表名
- 3D可视化展示调用链，支持缩放、旋转和交互
- 提供影响分析功能，评估修改某个存储过程的潜在影响
- 实时监控系统性能，自动告警异常情况

## 许可证

本项目采用MIT许可证