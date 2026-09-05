/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// 扩展 vue-router 的 RouteMeta,支持菜单/角色等
declare module 'vue-router' {
  interface RouteMeta {
    title?: string;
    public?: boolean;
    requireRole?: string;
    menu?: { icon?: string; order: number };
    hideInMenu?: boolean;
  }
}

// Vue SFC 类型
declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}
