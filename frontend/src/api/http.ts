// axios 实例:统一 baseURL + withCredentials(带 cookie)+ 请求拦截加 X-Role + 响应拦截按 code 分流
// 设计:不 import auth store,改读 sessionStorage(与 auth store 的 persist key 'sc-auth' 对齐),避免循环 import
import axios from 'axios';
import { ElMessage } from 'element-plus';
import type { ApiResp } from './types';

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE,
  withCredentials: true,
  timeout: 15000,
});

// 请求拦截:从 sessionStorage 读 role,注入 X-Role 头(后端 deps.py 据此精确匹配角色 cookie)
http.interceptors.request.use((config) => {
  const role = getRoleFromStorage();
  if (role) config.headers['X-Role'] = role;
  return config;
});

// 响应拦截:后端 HTTP 始终 200,按 json.code 判断(见 app/core/exception.py:31-52)
http.interceptors.response.use(
  (res) => {
    const body = res.data as ApiResp;
    if (body.code === 0) return body.data;
    if (body.code === 401) {
      // 登录失效:清 storage + 整页跳登录(避免内存 store 残留)
      clearAuthStorage();
      redirectLogin();
      return Promise.reject(new ApiError(body.code, body.message));
    }
    ElMessage.error(body.message || '请求失败');
    return Promise.reject(new ApiError(body.code, body.message));
  },
  (err) => {
    ElMessage.error('网络异常,请确认后端已启动');
    return Promise.reject(err);
  },
);

function getRoleFromStorage(): string {
  try {
    const raw = sessionStorage.getItem('sc-auth');
    if (!raw) return '';
    const parsed = JSON.parse(raw);
    return parsed.role || '';
  } catch {
    return '';
  }
}

function clearAuthStorage() {
  sessionStorage.removeItem('sc-auth');
}

function redirectLogin() {
  const redirect = encodeURIComponent(location.pathname + location.search);
  location.href = `/login?redirect=${redirect}`;
}

export class ApiError extends Error {
  code: number;
  constructor(code: number, message: string) {
    super(message);
    this.code = code;
    this.name = 'ApiError';
  }
}

export default http;
