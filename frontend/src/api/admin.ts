import http from './http';
import type {
  AdminOverview,
  AdminUser,
  AdminCourse,
  AdminClass,
  AdminEnrollment,
  AdminSchedule,
  AdminAudit,
  AdminStat,
} from './types';

export const adminApi = {
  // 数据看板
  overview: () => http.get<AdminOverview>('/admin/stat/overview'),

  // 人员管理
  listUsers: (params: {
    role: 'student' | 'teacher' | 'counselor' | 'admin';
    keyword?: string;
    page?: number;
    page_size?: number;
  }) => http.get<{ total: number; items: AdminUser[] }>('/admin/users', { params }),

  createUser: (payload: {
    role: 'student' | 'teacher' | 'counselor';
    user_no: string;
    name: string;
    gender?: number;
    phone?: string;
    email?: string;
    class_id?: string;
    department?: string;
    title?: string;
    password?: string;
  }) => http.post<AdminUser>('/admin/users', payload),

  updateUser: (
    role: string,
    userId: string,
    payload: Partial<{
      name: string;
      gender: number;
      phone: string;
      email: string;
      class_id: string;
      department: string;
      title: string;
      status: number;
    }>,
  ) => http.put<AdminUser>(`/admin/users/${role}/${userId}`, payload),

  resetPassword: (role: string, userId: string) =>
    http.post<{ user_id: string; role: string }>(
      `/admin/users/${role}/${userId}/reset-password`,
    ),

  toggleStatus: (role: string, userId: string) =>
    http.post<{ user_id: string; role: string; status: number }>(
      `/admin/users/${role}/${userId}/toggle-status`,
    ),

  deleteUser: (role: string, userId: string) =>
    http.delete<{ user_id: string; role: string }>(
      `/admin/users/${role}/${userId}`,
    ),

  // 课程管理
  listCourses: () => http.get<AdminCourse[]>('/admin/courses'),

  createCourse: (payload: {
    course_id: string;
    course_name: string;
    credit?: number;
    hours?: number;
    description?: string;
    semester?: string;
    teacher_id: string;
    status?: number;
  }) => http.post<{ course_id: string }>('/admin/courses', payload),

  updateCourse: (
    courseId: string,
    payload: Partial<{
      course_name: string;
      credit: number;
      hours: number;
      description: string;
      semester: string;
      teacher_id: string;
      status: number;
    }>,
  ) => http.put<{ course_id: string }>(`/admin/courses/${courseId}`, payload),

  deleteCourse: (courseId: string) =>
    http.delete<{ course_id: string }>(`/admin/courses/${courseId}`),

  // 班级管理
  listClasses: () => http.get<AdminClass[]>('/admin/classes'),

  createClass: (payload: {
    class_id: string;
    class_name: string;
    grade?: string;
    major?: string;
    department?: string;
  }) => http.post<{ class_id: string }>('/admin/classes', payload),

  updateClass: (
    classId: string,
    payload: Partial<{
      class_name: string;
      grade: string;
      major: string;
      department: string;
    }>,
  ) => http.put<{ class_id: string }>(`/admin/classes/${classId}`, payload),

  // 选课管理
  listEnrollments: (courseId?: string) =>
    http.get<AdminEnrollment[]>('/admin/enrollments', {
      params: { course_id: courseId || undefined },
    }),

  createEnrollment: (payload: { course_id: string; student_no: string }) =>
    http.post<{ id: number }>('/admin/enrollments', payload),

  deleteEnrollment: (enrollId: number) =>
    http.delete<{ id: number }>(`/admin/enrollments/${enrollId}`),

  // 课表管理
  listSchedules: (params: { class_id?: string; weekday?: number }) =>
    http.get<AdminSchedule[]>('/admin/schedules', { params }),

  createSchedule: (payload: {
    course_id: string;
    class_id: string;
    weekday: number;
    start_time: string;
    end_time: string;
    weeks?: string;
    classroom?: string;
  }) => http.post<{ id: number }>('/admin/schedules', payload),

  deleteSchedule: (scheduleId: number) =>
    http.delete<{ id: number }>(`/admin/schedules/${scheduleId}`),

  // 审计日志
  listAudit: (params: { page?: number; page_size?: number; action?: string }) =>
    http.get<{ total: number; items: AdminAudit[] }>('/admin/audit', {
      params,
    }),

  // 数据统计（复用 overview）
  stat: () => http.get<AdminStat>('/admin/stat/overview'),
};
