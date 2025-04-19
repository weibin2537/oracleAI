// frontend/src/services/api.js
import axios from 'axios';

const API_BASE_URL = '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default {
  /**
   * 获取存储过程详细信息
   * @param {string} procedureName - 存储过程名称
   * @returns {Promise} - API响应
   */
  getProcedureDetails(procedureName) {
    return apiClient.get(`/procedure/${procedureName}`);
  },
  
  /**
   * 获取存储过程调用链
   * @param {string} procedureName - 存储过程名称
   * @param {number} depth - 调用深度
   * @param {number} confidence - 最小置信度
   * @returns {Promise} - API响应
   */
  getCallChain(procedureName, depth = 3, confidence = 0.5) {
    return apiClient.get(`/call-chain/${procedureName}`, {
      params: { depth, confidence }
    });
  },
  
  /**
   * 获取存储过程风险评估
   * @param {string} procedureName - 存储过程名称
   * @returns {Promise} - API响应
   */
  getRiskAssessment(procedureName) {
    return apiClient.get(`/risk/${procedureName}`);
  },
  
  /**
   * 搜索存储过程
   * @param {string} keyword - 搜索关键词
   * @param {number} limit - 结果数量限制
   * @returns {Promise} - API响应
   */
  searchProcedures(keyword, limit = 20) {
    return apiClient.get('/search', {
      params: { keyword, limit }
    });
  },
  
  /**
   * 获取存储过程影响分析
   * @param {string} procedureName - 存储过程名称
   * @param {number} depth - 分析深度
   * @returns {Promise} - API响应
   */
  getImpactAnalysis(procedureName, depth = 5) {
    return apiClient.get(`/impact/${procedureName}`, {
      params: { depth }
    });
  }
};