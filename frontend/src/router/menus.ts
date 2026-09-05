import type { Role } from '@/api/types';
import { routes } from './routes';

export interface MenuItem {
  path: string;
  title: string;
  icon?: string;
  order: number;
}

// 从路由 children 派生菜单(过滤 hideInMenu,按 order 排序)
export function getMenus(role: Role | ''): MenuItem[] {
  if (!role) return [];
  const root = routes.find((r) => r.path === `/${role}`);
  if (!root || !root.children) return [];
  const items: MenuItem[] = [];
  for (const c of root.children) {
    if (c.meta?.menu && !c.meta?.hideInMenu) {
      const childPath = c.path === '' ? '' : `/${c.path}`;
      items.push({
        path: `/${role}${childPath}`,
        title: c.meta.title || '',
        icon: c.meta.menu.icon,
        order: c.meta.menu.order,
      });
    }
  }
  return items.sort((a, b) => a.order - b.order);
}
