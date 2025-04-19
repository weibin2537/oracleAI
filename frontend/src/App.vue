// frontend/src/App.vue
<template>
  <div class="app">
    <header class="header">
      <h1>Oracle存储过程3D调用链分析图谱系统</h1>
      <div class="actions">
        <button @click="showUploadDialog">上传存储过程</button>
        <button @click="showHelpDialog">帮助</button>
      </div>
    </header>
    
    <main class="main">
      <div class="sidebar">
        <div class="search-panel">
          <h3>快速搜索</h3>
          <div class="search-input">
            <input 
              v-model="searchTerm" 
              type="text" 
              placeholder="搜索存储过程..."
              @keyup.enter="search"
            />
            <button @click="search">搜索</button>
          </div>
          <div v-if="searchResults.length > 0" class="search-results">
            <h4>搜索结果</h4>
            <ul>
              <li 
                v-for="result in searchResults" 
                :key="result.name"
                @click="loadCallChain(result.name)"
              >
                <span class="name">{{ result.name }}</span>
                <span class="schema">{{ result.schema }}</span>
              </li>
            </ul>
          </div>
        </div>
        
        <div class="recent-panel">
          <h3>最近访问</h3>
          <ul v-if="recentProcedures.length > 0">
            <li 
              v-for="proc in recentProcedures" 
              :key="proc.name"
              @click="loadCallChain(proc.name)"
            >
              {{ proc.name }}
            </li>
          </ul>
          <p v-else>暂无最近访问记录</p>
        </div>
      </div>
      
      <div class="content">
        <Graph3D 
          ref="graph3d"
          :initial-data="graphData"
          :api-base-url="apiBaseUrl"
          @node-selected="handleNodeSelected"
        />
      </div>
    </main>
    
    <!-- 上传对话框 -->
    <div v-if="showUpload" class="dialog-overlay">
      <div class="dialog">
        <h2>上传存储过程文件</h2>
        <div class="upload-area">
          <input 
            type="file" 
            accept=".sql,.pls,.plb,.bdy"
            multiple
            @change="handleFileUpload"
          />
          <p class="help-text">支持 .sql, .pls, .plb, .bdy 格式文件</p>
        </div>
        <div class="dialog-actions">
          <button @click="uploadFiles" :disabled="!selectedFiles.length">上传</button>
          <button class="cancel" @click="cancelUpload">取消</button>
        </div>
      </div>
    </div>
    
    <!-- 帮助对话框 -->
    <div v-if="showHelp" class="dialog-overlay">
      <div class="dialog help-dialog">
        <h2>系统帮助</h2>
        <div class="help-content">
          <h3>基本操作</h3>
          <ul>
            <li><strong>搜索</strong>: 输入存储过程名称搜索</li>
            <li><strong>查看调用链</strong>: 点击搜索结果加载调用链</li>
            <li><strong>节点交互</strong>: 点击节点查看详细信息</li>
            <li><strong>调整视图</strong>: 使用鼠标滚轮缩放，拖拽旋转</li>
          </ul>
          
          <h3>图谱说明</h3>
          <ul>
            <li><strong>红色节点</strong>: 存储过程</li>
            <li><strong>蓝色节点</strong>: 表</li>
            <li><strong>橙色节点</strong>: 动态表</li>
            <li><strong>紫色连线</strong>: 调用关系</li>
            <li><strong>绿色连线</strong>: 引用关系</li>
          </ul>
          
          <h3>快捷键</h3>
          <ul>
            <li><strong>空格</strong>: 重置视图</li>
            <li><strong>Esc</strong>: 取消选择</li>
          </ul>
        </div>
        <div class="dialog-actions">
          <button @click="showHelp = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import Graph3D from './components/Graph3D.vue';
import api from './services/api';

export default {
  name: 'App',
  components: {
    Graph3D
  },
  setup() {
    const searchTerm = ref('');
    const searchResults = ref([]);
    const recentProcedures = ref([]);
    const graphData = ref({ nodes: [], links: [] });
    const apiBaseUrl = ref('/api');
    const graph3d = ref(null);
    
    // 上传相关
    const showUpload = ref(false);
    const selectedFiles = ref([]);
    
    // 帮助相关
    const showHelp = ref(false);
    
    // 初始化
    onMounted(() => {
      // 加载最近访问记录
      loadRecentProcedures();
      
      // 监听键盘事件
      document.addEventListener('keydown', handleKeyDown);
    });
    
    // 加载最近访问的存储过程
    const loadRecentProcedures = () => {
      const recent = localStorage.getItem('recentProcedures');
      if (recent) {
        try {
          recentProcedures.value = JSON.parse(recent);
        } catch (error) {
          console.error('解析最近访问记录失败', error);
          recentProcedures.value = [];
        }
      }
    };
    
    // 添加到最近访问
    const addToRecentProcedures = (procedure) => {
      // 检查是否已存在
      const index = recentProcedures.value.findIndex(p => p.name === procedure.name);
      if (index !== -1) {
        // 已存在，移到最前面
        recentProcedures.value.splice(index, 1);
      }
      // frontend/src/App.vue (continued)
      // 已存在，移到最前面
      recentProcedures.value.splice(index, 1);
      
      // 添加到最前面
      recentProcedures.value.unshift(procedure);
      
      // 只保留最近10个
      if (recentProcedures.value.length > 10) {
        recentProcedures.value = recentProcedures.value.slice(0, 10);
      }
      
      // 保存到本地存储
      localStorage.setItem('recentProcedures', JSON.stringify(recentProcedures.value));
    };
    
    // 搜索存储过程
    const search = async () => {
      if (!searchTerm.value) return;
      
      try {
        const response = await api.searchProcedures(searchTerm.value);
        searchResults.value = response.data.procedures || [];
      } catch (error) {
        console.error('搜索失败', error);
        alert('搜索失败，请重试');
      }
    };
    
    // 加载调用链
    const loadCallChain = async (procedureName) => {
      try {
        // 显示加载中状态
        // TODO: 添加加载指示器
        
        // 调用API获取调用链数据
        const response = await api.getCallChain(procedureName);
        graphData.value = response.data;
        
        // 添加到最近访问
        addToRecentProcedures({ name: procedureName });
        
        // 如果有Graph3D组件引用，可以直接调用其方法
        if (graph3d.value) {
          // 假设Graph3D组件有一个loadData方法
          graph3d.value.loadData(response.data);
        }
      } catch (error) {
        console.error('加载调用链失败', error);
        alert('加载调用链失败，请重试');
      }
    };
    
    // 处理节点选中事件
    const handleNodeSelected = (node) => {
      console.log('节点被选中', node);
      // 可以在这里添加处理逻辑
    };
    
    // 显示上传对话框
    const showUploadDialog = () => {
      showUpload.value = true;
    };
    
    // 取消上传
    const cancelUpload = () => {
      showUpload.value = false;
      selectedFiles.value = [];
    };
    
    // 处理文件选择
    const handleFileUpload = (event) => {
      selectedFiles.value = Array.from(event.target.files);
    };
    
    // 上传文件
    const uploadFiles = async () => {
      if (selectedFiles.value.length === 0) return;
      
      const formData = new FormData();
      selectedFiles.value.forEach(file => {
        formData.append('files', file);
      });
      
      try {
        // 假设有一个上传API
        const response = await fetch(`${apiBaseUrl.value}/upload`, {
          method: 'POST',
          body: formData
        });
        
        if (!response.ok) {
          throw new Error('上传失败');
        }
        
        const result = await response.json();
        
        alert(`成功上传 ${result.success_count} 个文件，解析失败 ${result.failed_count} 个文件`);
        
        // 关闭对话框
        cancelUpload();
        
        // 如果有新解析的存储过程，加载第一个
        if (result.procedures && result.procedures.length > 0) {
          loadCallChain(result.procedures[0].name);
        }
      } catch (error) {
        console.error('上传失败', error);
        alert('上传失败，请重试');
      }
    };
    
    // 显示帮助对话框
    const showHelpDialog = () => {
      showHelp.value = true;
    };
    
    // 处理键盘事件
    const handleKeyDown = (event) => {
      // 按空格键重置视图
      if (event.key === ' ' && !event.target.tagName.match(/INPUT|TEXTAREA/i)) {
        if (graph3d.value) {
          graph3d.value.resetCamera();
        }
        event.preventDefault();
      }
      
      // 按ESC键取消选择
      if (event.key === 'Escape') {
        if (graph3d.value) {
          graph3d.value.closeDetails();
        }
      }
    };
    
    return {
      searchTerm,
      searchResults,
      recentProcedures,
      graphData,
      apiBaseUrl,
      graph3d,
      showUpload,
      showHelp,
      selectedFiles,
      search,
      loadCallChain,
      handleNodeSelected,
      showUploadDialog,
      cancelUpload,
      handleFileUpload,
      uploadFiles,
      showHelpDialog
    };
  }
};
</script>

<style>
/* 全局样式 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  line-height: 1.6;
  color: #333;
  background-color: #f8f9fa;
}

.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* 头部样式 */
.header {
  background-color: #007bff;
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h1 {
  font-size: 1.5rem;
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 1rem;
}

.actions button {
  background-color: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.actions button:hover {
  background-color: rgba(255, 255, 255, 0.3);
}

/* 主内容区样式 */
.main {
  display: flex;
  flex: 1;
}

.sidebar {
  width: 300px;
  background-color: white;
  border-right: 1px solid #dee2e6;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.content {
  flex: 1;
  padding: 1rem;
}

/* 搜索面板样式 */
.search-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.search-panel h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #007bff;
  margin-bottom: 0.5rem;
}

.search-input {
  display: flex;
  gap: 0.5rem;
}

.search-input input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid #ced4da;
  border-radius: 4px;
}

.search-input button {
  background-color: #007bff;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.search-results {
  background-color: #f8f9fa;
  border-radius: 4px;
  padding: 0.5rem;
}

.search-results h4 {
  font-size: 0.9rem;
  color: #6c757d;
  margin-bottom: 0.5rem;
}

.search-results ul {
  list-style-type: none;
}

.search-results li {
  padding: 0.5rem;
  border-bottom: 1px solid #dee2e6;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
}

.search-results li:last-child {
  border-bottom: none;
}

.search-results li:hover {
  background-color: #e9ecef;
}

.search-results .name {
  font-weight: 500;
}

.search-results .schema {
  color: #6c757d;
  font-size: 0.8rem;
}

/* 最近访问面板样式 */
.recent-panel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.recent-panel h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #007bff;
  margin-bottom: 0.5rem;
}

.recent-panel ul {
  list-style-type: none;
}

.recent-panel li {
  padding: 0.5rem;
  border-bottom: 1px solid #dee2e6;
  cursor: pointer;
}

.recent-panel li:last-child {
  border-bottom: none;
}

.recent-panel li:hover {
  background-color: #e9ecef;
}

/* 对话框样式 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.dialog {
  background-color: white;
  border-radius: 8px;
  padding: 2rem;
  width: 90%;
  max-width: 600px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.dialog h2 {
  font-size: 1.5rem;
  margin-bottom: 1.5rem;
  color: #007bff;
}

.upload-area {
  margin-bottom: 1.5rem;
}

.help-text {
  margin-top: 0.5rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
}

.dialog-actions button {
  padding: 0.5rem 1.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.dialog-actions button:not(.cancel) {
  background-color: #007bff;
  color: white;
}

.dialog-actions button:not(.cancel):hover {
  background-color: #0069d9;
}

.dialog-actions button.cancel {
  background-color: #6c757d;
  color: white;
}

.dialog-actions button.cancel:hover {
  background-color: #5a6268;
}

.dialog-actions button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

/* 帮助对话框样式 */
.help-dialog {
  max-width: 800px;
}

.help-content {
  margin-bottom: 1.5rem;
}

.help-content h3 {
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: #007bff;
}

.help-content ul {
  list-style-type: disc;
  padding-left: 1.5rem;
  margin-bottom: 1rem;
}

.help-content li {
  margin-bottom: 0.5rem;
}
</style>