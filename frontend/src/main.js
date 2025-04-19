// frontend/src/main.js
import { createApp } from 'vue';
import App from './App.vue';
import './assets/style.css';

const app = createApp(App);

// 添加全局错误处理
app.config.errorHandler = (err, vm, info) => {
  console.error('Vue全局错误:', err);
  console.error('信息:', info);
};

app.mount('#app');