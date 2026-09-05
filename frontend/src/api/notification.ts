import http from './http';
import type { NotificationListResp } from './types';

export const notificationApi = {
  list: (limit = 20) =>
    http.get<NotificationListResp>('/notification/list', { params: { limit } }),
  read: (id: number) => http.post(`/notification/read/${id}`),
  readAll: () => http.post('/notification/read-all'),
};
