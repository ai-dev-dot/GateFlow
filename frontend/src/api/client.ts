import axios from 'axios';
import { message } from 'antd';

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：自动添加 Bearer token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// 响应拦截器：统一错误处理
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    if (status === 401) {
      // 清除本地 token 并跳转登录页
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    } else if (status === 403) {
      message.error('权限不足，无法执行此操作');
    } else if (status === 500) {
      message.error('服务器内部错误，请稍后重试');
    } else {
      const msg =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        '请求失败';
      message.error(msg);
    }

    return Promise.reject(error);
  },
);

export default client;
