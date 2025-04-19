// frontend/src/components/Graph3D.vue
<template>
  <div>
    <div ref="graphContainer" class="graph-container"></div>
    <div class="controls">
      <div class="search-box">
        <input 
          v-model="searchTerm" 
          type="text" 
          placeholder="搜索节点..."
          @keyup.enter="searchNode"
        />
        <button @click="searchNode">搜索</button>
      </div>
      <div class="sliders">
        <div class="slider-container">
          <label>调用链深度: {{ depth }}</label>
          <input 
            v-model.number="depth" 
            type="range" 
            min="1" 
            max="5" 
            @change="depthChanged"
          />
        </div>
        <div class="slider-container">
          <label>置信度阈值: {{ confidenceThreshold.toFixed(1) }}</label>
          <input 
            v-model.number="confidenceThreshold" 
            type="range" 
            min="0" 
            max="1" 
            step="0.1"
            @change="confidenceChanged"
          />
        </div>
      </div>
      <div class="view-controls">
        <button @click="toggleView">{{ is3D ? '2D 视图' : '3D 视图' }}</button>
        <button @click="resetCamera">重置视图</button>
        <button @click="exportImage">导出图像</button>
      </div>
      <div class="legend">
        <div class="legend-item">
          <div class="color-box sp-color"></div>
          <span>存储过程</span>
        </div>
        <div class="legend-item">
          <div class="color-box table-color"></div>
          <span>表</span>
        </div>
        <div class="legend-item">
          <div class="color-box dyn-table-color"></div>
          <span>动态表</span>
        </div>
        <div class="legend-item">
          <div class="color-box calls-color"></div>
          <span>调用关系</span>
        </div>
        <div class="legend-item">
          <div class="color-box ref-color"></div>
          <span>引用关系</span>
        </div>
      </div>
    </div>
    <div v-if="selectedNode" class="node-details">
      <h3>{{ selectedNode.name }}</h3>
      <p><strong>类型:</strong> {{ selectedNode.type }}</p>
      <p v-if="selectedNode.schema"><strong>模式:</strong> {{ selectedNode.schema }}</p>
      <p v-if="selectedNode.type === 'SP'"><strong>复杂度:</strong> {{ selectedNode.complexity }}</p>
      <p v-if="selectedNode.type === 'TABLE' && selectedNode.is_core" class="core-table">核心表</p>
      <div v-if="selectedNode.confidence" class="confidence">
        <p><strong>置信度:</strong> {{ (selectedNode.confidence * 100).toFixed(0) }}%</p>
        <div class="confidence-bar">
          <div class="confidence-fill" :style="{ width: (selectedNode.confidence * 100) + '%' }"></div>
        </div>
      </div>
      <button @click="loadDetails(selectedNode.id)">加载详细信息</button>
      <button @click="analyzeImpact(selectedNode.id)">影响分析</button>
      <button @click="closeDetails">关闭</button>
    </div>
  </div>
</template>

<script>
import { ForceGraph3D } from 'three-forcegraph';
import { ForceGraph2D } from 'force-graph';
import SpriteText from 'three-spritetext';
import * as THREE from 'three';
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { saveAs } from 'file-saver';

export default {
  name: 'Graph3D',
  props: {
    initialData: {
// frontend/src/components/Graph3D.vue (continued)
type: Object,
      required: true
    },
    apiBaseUrl: {
      type: String,
      default: '/api'
    }
  },
  setup(props) {
    const graphContainer = ref(null);
    const searchTerm = ref('');
    const selectedNode = ref(null);
    const graph = ref(null);
    const graphData = ref({ nodes: [], links: [] });
    const depth = ref(3);
    const confidenceThreshold = ref(0.5);
    const is3D = ref(true);
    
    // 初始化图谱
    onMounted(() => {
      initGraph();
      if (props.initialData) {
        loadData(props.initialData);
      }
    });
    
    // 清理资源
    onBeforeUnmount(() => {
      if (graph.value) {
        graph.value._destructor();
      }
    });
    
    // 初始化图谱
    const initGraph = () => {
      const container = graphContainer.value;
      if (!container) return;
      
      if (is3D.value) {
        // 3D 图谱
        graph.value = ForceGraph3D()
          .backgroundColor('#111')
          .nodeLabel(node => getNodeTooltip(node))
          .nodeColor(node => getNodeColor(node))
          .nodeThreeObject(node => createNodeObject(node))
          .linkLabel(link => getLinkTooltip(link))
          .linkColor(link => getLinkColor(link))
          .linkWidth(link => getLinkWidth(link))
          .linkDirectionalArrowLength(5)
          .linkDirectionalArrowRelPos(1)
          .linkDirectionalParticles(link => link.type === 'CALLS' ? 3 : 1)
          .linkDirectionalParticleSpeed(0.003)
          .onNodeClick(handleNodeClick)
          .onBackgroundClick(clearSelection)(container);
      } else {
        // 2D 图谱
        graph.value = ForceGraph2D()
          .backgroundColor('#111')
          .nodeLabel(node => getNodeTooltip(node))
          .nodeColor(node => getNodeColor(node))
          .nodeCanvasObject((node, ctx, globalScale) => createNodeCanvas(node, ctx, globalScale))
          .linkLabel(link => getLinkTooltip(link))
          .linkColor(link => getLinkColor(link))
          .linkWidth(link => getLinkWidth(link))
          .linkDirectionalArrowLength(5)
          .linkDirectionalArrowRelPos(1)
          .linkDirectionalParticles(link => link.type === 'CALLS' ? 3 : 1)
          .linkDirectionalParticleSpeed(0.003)
          .onNodeClick(handleNodeClick)
          .onBackgroundClick(clearSelection)(container);
      }
      
      // 设置初始视角
      if (is3D.value) {
        graph.value.cameraPosition({ z: 250 });
      }
    };
    
    // 加载图谱数据
    const loadData = (data) => {
      graphData.value = data;
      graph.value.graphData(data);
    };
    
    // 获取节点颜色
    const getNodeColor = (node) => {
      if (node.type === 'SP') return '#e74c3c';  // 红色
      if (node.type === 'TABLE') return '#3498db'; // 蓝色
      if (node.type === 'DYN_TABLE') return '#f39c12'; // 橙色
      return '#95a5a6'; // 默认灰色
    };
    
    // 获取链接颜色
    const getLinkColor = (link) => {
      if (link.confidence < confidenceThreshold.value) {
        return '#e74c3c'; // 红色，置信度低
      }
      if (link.type === 'CALLS') return '#9b59b6'; // 紫色
      if (link.type === 'REFERENCES') return '#2ecc71'; // 绿色
      if (link.type === 'DYN_REFERENCES') return '#f39c12'; // 橙色
      return '#95a5a6'; // 默认灰色
    };
    
    // 获取链接宽度
    const getLinkWidth = (link) => {
      return (link.confidence || 0.5) * 3; // 根据置信度调整宽度
    };
    
    // 创建节点对象（3D）
    const createNodeObject = (node) => {
      // 使用SpriteText显示节点名称
      const sprite = new SpriteText(node.name);
      sprite.color = getNodeColor(node);
      sprite.textHeight = 8;
      sprite.backgroundColor = 'rgba(0,0,0,0.7)';
      sprite.padding = 2;
      sprite.borderRadius = 3;
      
      // 创建节点球体
      const geometry = new THREE.SphereGeometry(node.type === 'SP' ? 5 : 4);
      const material = new THREE.MeshLambertMaterial({
        color: getNodeColor(node),
        transparent: true,
        opacity: node.confidence || 1
      });
      const mesh = new THREE.Mesh(geometry, material);
      
      // 组合成一个组
      const group = new THREE.Group();
      group.add(mesh);
      
      // 将文本精灵放在球体上方
      sprite.position.y = 8;
      group.add(sprite);
      
      return group;
    };
    
    // 创建节点画布（2D）
    const createNodeCanvas = (node, ctx, globalScale) => {
      const size = node.type === 'SP' ? 10 : 8;
      const fontSize = 12 / globalScale;
      const label = node.name;
      
      // 绘制节点
      ctx.beginPath();
      ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
      ctx.fillStyle = getNodeColor(node);
      ctx.fill();
      
      // 绘制边框
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 0.5;
      ctx.stroke();
      
      // 绘制文本
      ctx.font = `${fontSize}px Sans-Serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffffff';
      ctx.fillText(label, node.x, node.y - size - fontSize);
    };
    
    // 获取节点提示文本
    const getNodeTooltip = (node) => {
      let tooltip = `<div class="tooltip">`;
      tooltip += `<div class="title">${node.name}</div>`;
      tooltip += `<div class="type">${node.type}</div>`;
      
      if (node.type === 'SP') {
        tooltip += `<div>复杂度: ${node.complexity || 'N/A'}</div>`;
        if (node.last_modified) {
          tooltip += `<div>最后修改: ${node.last_modified}</div>`;
        }
      }
      
      if (node.type === 'TABLE' || node.type === 'DYN_TABLE') {
        if (node.schema) {
          tooltip += `<div>模式: ${node.schema}</div>`;
        }
        if (node.is_core) {
          tooltip += `<div class="warning">核心表</div>`;
        }
      }
      
      if (node.confidence) {
        tooltip += `<div>置信度: ${(node.confidence * 100).toFixed(0)}%</div>`;
      }
      
      tooltip += `</div>`;
      return tooltip;
    };
    
    // 获取链接提示文本
    const getLinkTooltip = (link) => {
      let tooltip = `<div class="tooltip">`;
      tooltip += `<div class="title">${link.type}</div>`;
      
      if (link.type === 'CALLS') {
        tooltip += `<div>深度: ${link.depth || 1}</div>`;
        if (link.frequency) {
          tooltip += `<div>频率: ${link.frequency}</div>`;
        }
      }
      
      if (link.type === 'REFERENCES' || link.type === 'DYN_REFERENCES') {
        if (link.operation) {
          tooltip += `<div>操作: ${link.operation}</div>`;
        }
        if (link.type === 'DYN_REFERENCES' && link.need_verify) {
          tooltip += `<div class="warning">需要验证</div>`;
        }
      }
      
      if (link.confidence) {
        tooltip += `<div>置信度: ${(link.confidence * 100).toFixed(0)}%</div>`;
      }
      
      tooltip += `</div>`;
      return tooltip;
    };
    
    // 处理节点点击事件
    const handleNodeClick = (node) => {
      selectedNode.value = node;
      highlightNode(node);
    };
    
    // 清除选择
    const clearSelection = () => {
      selectedNode.value = null;
      resetHighlight();
    };
    
    // 高亮节点及相关链接
    const highlightNode = (node) => {
      const { nodes, links } = graphData.value;
      
      // 重置所有节点和链接的透明度
      nodes.forEach(n => {
        n.__highlighted = false;
        n.__opacity = 0.2;
      });
      
      links.forEach(l => {
        l.__highlighted = false;
        l.__opacity = 0.1;
      });
      
      // 高亮选中的节点
      node.__highlighted = true;
      node.__opacity = 1;
      
      // 查找相关链接和节点
      const connectedLinks = links.filter(l => l.source === node || l.target === node);
      connectedLinks.forEach(l => {
        l.__highlighted = true;
        l.__opacity = 1;
        
        // 高亮链接的另一端节点
        const connectedNode = l.source === node ? l.target : l.source;
        connectedNode.__highlighted = true;
        connectedNode.__opacity = 0.8;
      });
      
      // 更新图谱
      updateNodesAppearance();
    };
    
    // 重置高亮
    const resetHighlight = () => {
      const { nodes, links } = graphData.value;
      
      nodes.forEach(n => {
        n.__highlighted = false;
        n.__opacity = 1;
      });
      
      links.forEach(l => {
        l.__highlighted = false;
        l.__opacity = 1;
      });
      
      updateNodesAppearance();
    };
    
    // 更新节点外观
    const updateNodesAppearance = () => {
      if (is3D.value) {
        // 更新3D节点
        graph.value
          .nodeThreeObjectExtend(false)
          .nodeThreeObject(node => createNodeObject(node))
          .linkOpacity(link => link.__opacity !== undefined ? link.__opacity : 1);
      } else {
        // 更新2D节点
        graph.value
          .nodeCanvasObject((node, ctx, globalScale) => createNodeCanvas(node, ctx, globalScale))
          .linkOpacity(link => link.__opacity !== undefined ? link.__opacity : 1);
      }
    };
    
    // 搜索节点
    const searchNode = async () => {
      if (!searchTerm.value) return;
      
      try {
        const response = await fetch(`${props.apiBaseUrl}/search?keyword=${encodeURIComponent(searchTerm.value)}`);
        const data = await response.json();
        
        if (data.procedures && data.procedures.length > 0) {
          // 找到匹配的节点
          const procedure = data.procedures[0];
          const node = graphData.value.nodes.find(n => n.name === procedure.name);
          
          if (node) {
            // 高亮节点
            handleNodeClick(node);
            
            // 聚焦到节点
            const distance = is3D.value ? 100 : 250;
            graph.value.centerAt(node.x, node.y, distance);
            
            if (is3D.value) {
              graph.value.cameraPosition(
                { x: node.x, y: node.y, z: distance },
                node,
                2000
              );
            }
          } else {
            // 如果节点不在当前图谱中，加载该节点的调用链
            loadCallChain(procedure.name);
          }
        } else {
          alert('未找到匹配的节点');
        }
      } catch (error) {
        console.error('搜索失败', error);
        alert('搜索失败，请重试');
      }
    };
    
    // 加载调用链
    const loadCallChain = async (nodeName) => {
      try {
        const response = await fetch(
          `${props.apiBaseUrl}/call-chain/${nodeName}?depth=${depth.value}&confidence=${confidenceThreshold.value}`
        );
        const data = await response.json();
        
        // 加载新数据
        loadData(data);
        
        // 查找并高亮目标节点
        const node = data.nodes.find(n => n.name === nodeName);
        if (node) {
          handleNodeClick(node);
        }
      } catch (error) {
        console.error('加载调用链失败', error);
        alert('加载调用链失败，请重试');
      }
    };
    
    // 加载节点详细信息
    const loadDetails = async (nodeId) => {
      try {
        const node = graphData.value.nodes.find(n => n.id === nodeId);
        if (!node) return;
        
        const response = await fetch(`${props.apiBaseUrl}/procedure/${node.name}`);
        const data = await response.json();
        
        // 显示详细信息（可以在这里添加更多逻辑）
        alert(`${node.name} 详细信息\n调用的存储过程: ${data.called_sps.length}\n引用的表: ${data.referenced_tables.length}`);
      } catch (error) {
        console.error('加载详细信息失败', error);
        alert('加载详细信息失败，请重试');
      }
    };
    
    // 分析影响
    const analyzeImpact = async (nodeId) => {
      try {
        const node = graphData.value.nodes.find(n => n.id === nodeId);
        if (!node) return;
        
        const response = await fetch(`${props.apiBaseUrl}/impact/${node.name}?depth=${depth.value}`);
        const data = await response.json();
        
        // 显示影响分析结果
        alert(`${node.name} 影响分析\n受影响节点总数: ${data.total_affected}\n受影响存储过程: ${data.affected_sps}\n受影响表: ${data.affected_tables}`);
      } catch (error) {
        console.error('影响分析失败', error);
        alert('影响分析失败，请重试');
      }
    };
    
    // 调用链深度改变
    const depthChanged = () => {
      if (selectedNode.value) {
        loadCallChain(selectedNode.value.name);
      }
    };
    
    // 置信度阈值改变
    const confidenceChanged = () => {
      // 更新链接颜色和宽度
      const { links } = graphData.value;
      links.forEach(link => {
        link.__opacity = link.confidence >= confidenceThreshold.value ? 1 : 0.3;
      });
      
      updateNodesAppearance();
    };
    
    // 切换2D/3D视图
    const toggleView = () => {
      is3D.value = !is3D.value;
      
      // 保存当前数据
      const currentData = graphData.value;
      
      // 清理当前图谱
      if (graph.value) {
        graph.value._destructor();
      }
      
      // 重新初始化
      initGraph();
      
      // 重新加载数据
      loadData(currentData);
    };
    
    // 重置相机位置
    const resetCamera = () => {
      if (is3D.value) {
        graph.value.cameraPosition({ x: 0, y: 0, z: 250 }, { x: 0, y: 0, z: 0 }, 1000);
      } else {
        graph.value.centerAt(0, 0, 1000);
        graph.value.zoom(1, 1000);
      }
    };
    
    // 导出图像
    const exportImage = () => {
      try {
        const canvas = graphContainer.value.querySelector('canvas');
        if (!canvas) return;
        
        canvas.toBlob(blob => {
          saveAs(blob, `oracle-sp-graph-${new Date().toISOString().slice(0, 10)}.png`);
        });
      } catch (error) {
        console.error('导出图像失败', error);
        alert('导出图像失败，请重试');
      }
    };
    
    // 关闭详细信息面板
    const closeDetails = () => {
      selectedNode.value = null;
    };
    
    return {
      graphContainer,
      searchTerm,
      selectedNode,
      depth,
      confidenceThreshold,
      is3D,
      searchNode,
      loadDetails,
      analyzeImpact,
      closeDetails,
      depthChanged,
      confidenceChanged,
      toggleView,
      resetCamera,
      exportImage
    };
  }
};
</script>

<style scoped>
.graph-container {
  width: 100%;
  height: 80vh;
  background-color: #111;
  position: relative;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
}

.search-box {
  display: flex;
  gap: 5px;
}

.search-box input {
  padding: 5px 10px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  width: 200px;
}

.sliders {
  display: flex;
  gap: 20px;
}

.slider-container {
  display: flex;
  flex-direction: column;
  width: 150px;
}

.view-controls {
  display: flex;
  gap: 5px;
}

button {
  padding: 5px 10px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:hover {
  background-color: #0069d9;
}

.legend {
  display: flex;
  gap: 15px;
  margin-left: auto;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.color-box {
  width: 15px;
  height: 15px;
  border-radius: 3px;
}

.sp-color {
  background-color: #e74c3c;
}

.table-color {
  background-color: #3498db;
}

.dyn-table-color {
  background-color: #f39c12;
}

.calls-color {
  background-color: #9b59b6;
}

.ref-color {
  background-color: #2ecc71;
}

.node-details {
  position: absolute;
  top: 20px;
  right: 20px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 5px;
  padding: 15px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.3);
  max-width: 300px;
}

.node-details h3 {
  margin-top: 0;
  border-bottom: 1px solid #ddd;
  padding-bottom: 5px;
}

.core-table {
  color: #e74c3c;
  font-weight: bold;
}

.confidence {
  margin: 10px 0;
}

.confidence-bar {
  height: 8px;
  background-color: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  background-color: #28a745;
  border-radius: 4px;
}

.tooltip {
  background-color: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  max-width: 200px;
}

.tooltip .title {
  font-weight: bold;
  margin-bottom: 5px;
}

.tooltip .type {
  font-style: italic;
  color: #aaa;
  margin-bottom: 5px;
}

.tooltip .warning {
  color: #f39c12;
  font-weight: bold;
}
</style>