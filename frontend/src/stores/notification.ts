import { defineStore } from 'pinia';
import { ElNotification } from 'element-plus';
import { notificationApi } from '@/api/notification';
import type { NotificationItem } from '@/api/types';

interface NotificationState {
  items: NotificationItem[];
  unreadCount: number;
  seenIds: Set<number>;
  timerId: number | null;
}

export const useNotificationStore = defineStore('notification', {
  state: () => ({
    items: [] as NotificationItem[],
    unreadCount: 0,
    seenIds: new Set<number>() as unknown as Set<number>,
    timerId: null as number | null,
  }),
  actions: {
    startPolling() {
      if (this.timerId !== null) return;
      this.refresh();
      this.timerId = window.setInterval(() => this.refresh(), 5000);
    },
    stopPolling() {
      if (this.timerId !== null) {
        clearInterval(this.timerId);
        this.timerId = null;
      }
    },
    async refresh() {
      try {
        const data = await notificationApi.list(20);
        this.items = data.items;
        this.unreadCount = data.unread_count;
        // 检测新消息弹横幅(迁移自 web/js/demo.js notifWatcher)
        data.items.forEach((n) => {
          if (!this.seenIds.has(n.id) && !n.is_read) {
            this.popNew(n);
          }
          this.seenIds.add(n.id);
        });
      } catch {
        /* 401 已由 http.ts 处理 */
      }
    },
    async markRead(id: number) {
      try {
        await notificationApi.read(id);
        const item = this.items.find((i) => i.id === id);
        if (item && !item.is_read) {
          item.is_read = 1;
          this.unreadCount = Math.max(0, this.unreadCount - 1);
        }
      } catch {
        /* 忽略 */
      }
    },
    async markAllRead() {
      try {
        await notificationApi.readAll();
        this.unreadCount = 0;
        this.items.forEach((i) => (i.is_read = 1));
      } catch {
        /* 忽略 */
      }
    },
    popNew(n: NotificationItem) {
      ElNotification({
        title: n.title || '新通知',
        message: n.content,
        type: 'info',
        position: 'top-right',
        duration: 8000,
      });
    },
  },
});
