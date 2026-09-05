import http from './http';
import type { LoginResp, MeResp, ClassOption, RegisterReq } from './types';

export const authApi = {
  login: (payload: { username: string; password: string }) =>
    http.post<LoginResp>('/auth/login', payload),
  logout: () => http.post('/auth/logout'),
  me: () => http.get<MeResp>('/auth/me'),
  register: (payload: RegisterReq) => http.post('/auth/register', payload),
  classOptions: () => http.get<ClassOption[]>('/auth/class-options'),
};
