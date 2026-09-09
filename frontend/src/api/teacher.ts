import http from './http';
import type {
  Course,
  CourseTeachingRow,
  CheckinSession,
  StartCheckinResp,
  DashboardData,
  ReviewResult,
} from './types';

export const teacherApi = {
  // 我的课程
  myCourses: () => http.get<Course[]>('/teacher/courses'),

  // 我的课程·上课安排(大学合班授课,按课程聚合:选课人数/教室/上课时间)
  courseTeaching: () => http.get<CourseTeachingRow[]>('/teacher/courses/teaching'),

  // 发起签到
  startCheckin: (payload: {
    course_id: string;
    lat?: number;
    lng?: number;
    range_meters: number;
    duration_minutes: number;
  }) => http.post<StartCheckinResp>('/teacher/checkin/start', payload),

  // 结束签到(未签学生补缺勤)
  endCheckin: (sessionId: number) =>
    http.post<CheckinSession>(`/teacher/checkin/${sessionId}/end`),

  // 会话历史(本人最近 50 条)
  listSessions: (courseId?: string) =>
    http.get<CheckinSession[]>('/teacher/checkin/sessions', {
      params: { course_id: courseId || undefined },
    }),

  // 签到看板
  dashboard: (sessionId: number) =>
    http.get<DashboardData>(`/teacher/checkin/dashboard/${sessionId}`),

  // 考勤导出 Excel(用 a 标签触发,浏览器自动带 cookie)
  exportUrl: (sessionId: number) =>
    `${import.meta.env.VITE_API_BASE}/teacher/checkin/${sessionId}/export`,

  // 补签/请假审核
  reviewAttendance: (
    recordId: number,
    payload: { action: 'approve' | 'reject'; remark: string },
  ) => http.post<ReviewResult>(`/teacher/checkin/attendance/${recordId}/review`, payload),

  // 授权学生重新注册人脸
  allowFaceRegen: (studentNo: string) =>
    http.put(`/teacher/student/${studentNo}/face-regen`),
};
