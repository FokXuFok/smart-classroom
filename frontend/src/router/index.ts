import { createRouter, createWebHistory } from 'vue-router';
import { routes } from './routes';
import { useAuthStore } from '@/stores/auth';

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// 守卫:未登录跳 /login,角色不匹配跳自己首页
router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // 公共路由(login / 404)
  if (to.meta.public) {
    // 已登录访问 /login → 跳自己首页
    if (to.path === '/login' && auth.isLoggedIn) return `/${auth.role}`;
    return true;
  }

  // 未登录:先尝试 /api/auth/me 校验(应对刷新 cookie 还在但 store 丢了)
  if (!auth.isLoggedIn) {
    const ok = await auth.fetchMe().catch(() => false);
    if (!ok) {
      return `/login?redirect=${encodeURIComponent(to.fullPath)}`;
    }
  }

  // 角色不匹配:跳自己首页
  const requireRole = to.matched.find((r) => r.meta.requireRole)?.meta
    .requireRole as string | undefined;
  if (requireRole && auth.role !== requireRole) {
    return `/${auth.role}`;
  }

  return true;
});

export default router;
