import type { Role } from '@/api/types';

// 角色 → 中文
export const ROLE_CN: Record<string, string> = {
  student: '学生',
  teacher: '教师',
  counselor: '辅导员',
  admin: '管理员',
};

// 角色对应的 Element Plus tag 类型
export const ROLE_TAG_TYPE: Record<string, '' | 'success' | 'info' | 'warning' | 'danger'> = {
  student: 'info',
  teacher: '',
  counselor: 'warning',
  admin: 'danger',
};

// 签到状态文案(后端 CheckinRecord.status)
export const ATT_STATUS_CN: Record<number, string> = {
  1: '正常',
  2: '迟到',
  3: '缺勤',
  4: '待复核',
};

// 通知类型 → 中文
export const NOTIF_TYPE_CN: Record<string, string> = {
  checkin: '签到',
  homework: '作业',
  interaction: '互动',
  warning: '预警',
  system: '系统',
  approval: '审批',
};

// 演示账号快捷登录(迁移自 web/index.html)
export const DEMO_ACCOUNTS: { label: string; username: string; password: string; role: Role }[] = [
  { label: '管理员 admin', username: 'admin', password: 'admin123', role: 'admin' },
  { label: '教师 T001', username: 'T001', password: '123456', role: 'teacher' },
  { label: '教师 T002', username: 'T002', password: '123456', role: 'teacher' },
  { label: '辅导员 C001', username: 'C001', password: '123456', role: 'counselor' },
  { label: '辅导员 C002', username: 'C002', password: '123456', role: 'counselor' },
];
