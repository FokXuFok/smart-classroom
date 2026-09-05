import { defineStore } from 'pinia';
import { authApi } from '@/api/auth';
import type { Role } from '@/api/types';

interface AuthState {
  role: Role | '';
  user_id: string;
  name: string;
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    role: '',
    user_id: '',
    name: '',
  }),
  getters: {
    isLoggedIn: (s) => !!s.role,
    homeRoute: (s) => `/${s.role}`,
    roleCn: (s) => ROLE_CN[s.role] || '',
  },
  actions: {
    async login(payload: { username: string; password: string }) {
      const data = await authApi.login(payload);
      this.$patch({ role: data.role, user_id: data.user_id, name: data.name });
      return data;
    },
    async fetchMe() {
      try {
        const data = await authApi.me();
        this.$patch({ role: data.role, user_id: data.user_id, name: data.name });
        return true;
      } catch {
        return false;
      }
    },
    async logout() {
      try {
        await authApi.logout();
      } catch {
        /* 忽略,继续清本地态 */
      }
      this.clear();
    },
    clear() {
      this.$reset();
    },
  },
  persist: {
    key: 'sc-auth',
    storage: sessionStorage,
    pick: ['role', 'user_id', 'name'],
  },
});

const ROLE_CN: Record<string, string> = {
  student: '学生',
  teacher: '教师',
  counselor: '辅导员',
  admin: '管理员',
};
