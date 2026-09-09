// 后端统一响应 + 关键数据类型镜像(手写,与后端 Pydantic 对齐)

export type Role = 'student' | 'teacher' | 'counselor' | 'admin';

export interface ApiResp<T = any> {
  code: number;
  message: string;
  data: T;
}

export interface LoginResp {
  role: Role;
  name: string;
  user_id: string;
}

export interface MeResp {
  user_id: string;
  role: Role;
  name: string;
}

export interface ClassOption {
  class_code: string;
  class_name: string;
}

export interface RegisterReq {
  username: string;
  password: string;
  name: string;
  role: 'student' | 'teacher';
  class_id?: string;
}

export interface NotificationItem {
  id: number;
  notif_type: string;
  title: string;
  content: string;
  related_id: number | null;
  course_id: string | null;
  is_read: number; // 0 未读 / 1 已读
  create_time: string;
}

export interface NotificationListResp {
  unread_count: number;
  items: NotificationItem[];
}

// 课程
export interface Course {
  course_id: string;
  course_name: string;
  credit: number | null;
  hours: number | null;
  semester: string | null;
  student_count?: number;
}

// 课程上课安排(大学合班授课:一门课一行,含教室/时间/选课人数)
export interface CourseTeachingSlot {
  weekday: number; // 1-7
  start_time: string; // HH:mm
  end_time: string; // HH:mm
  weeks: string | null;
  classroom: string | null;
}

export interface CourseTeachingRow {
  course_id: string;
  course_name: string;
  credit: number | null;
  hours: number | null;
  semester: string | null;
  class_id: string | null; // 预留(合班模型下为空)
  class_name: string | null;
  student_count: number; // 课程选课人数
  classroom: string | null;
  classrooms: string[];
  times: CourseTeachingSlot[];
  arranged: boolean; // 是否有课表排课(教室/时间)
}

// 签到会话
export interface CheckinSession {
  id: number;
  course_id: string;
  teacher_id?: string;
  teacher_lat: number;
  teacher_lng: number;
  range_meters: number;
  duration_minutes: number;
  status: number; // 1 进行中 / 0 已结束
  create_time: string;
  end_time: string | null;
  course_name?: string;
  signed_count?: number;
  // end 返回的额外字段
  student_total?: number;
  absent_created?: number;
  stats?: Record<string, number>;
}

// 发起签到返回
export interface StartCheckinResp extends CheckinSession {
  deadline: string;
  used_default: boolean;
}

// 看板学生行
export interface DashboardStudent {
  record_id: number | null;
  review_remark: string | null;
  student_no: string;
  name: string;
  status: string; // 中文:正常/迟到/缺勤/未签到
  check_in_time: string | null;
  similarity1: number | null;
  location: string | null;
  distance_hint: number | null;
  review_status: number | null; // 0 无需 / 1 待审核 / 2 已审核
}

// 看板数据
export interface DashboardData {
  session: CheckinSession;
  students: DashboardStudent[];
}

// 审核结果
export interface ReviewResult {
  id: number;
  status: string;
  check_in_type: number | null;
  review_status: number;
  review_remark: string | null;
}

// SSE 事件类型
export interface SseSnapshot {
  type: 'snapshot';
  session_status: number;
  enrolled: number;
  review_pending: number;
  stats: Record<string, number>;
}

export interface SseCheckin {
  type: 'checkin';
  student_no: string;
  name: string;
  status: number;
  status_cn: string;
  check_in_time: string;
  similarity: number;
}

export interface SseReview {
  type: 'review';
  student_no: string;
  name: string;
  reason: string;
}

export interface SseReviewDone {
  type: 'review_done';
  record_id: number;
  student_id: string;
  status_cn: string;
  remark: string;
}

export interface SseSessionEnd {
  type: 'session_end';
  session_id: number;
  status: number;
  student_total: number;
  absent_created: number;
  stats: Record<string, number>;
}

export type SseEvent =
  | SseSnapshot
  | SseCheckin
  | SseReview
  | SseReviewDone
  | SseSessionEnd;

// 作业
export interface Homework {
  id: number;
  course_id: string;
  title: string;
  programming_language: string;
  max_score: number;
  deadline: string | null;
  allow_late_submit: number;
  status: number;
  feedback_visible: number;
  test_case_count: number;
  submit_count: number;
  student_count: number;
}

export interface TestCase {
  id?: number;
  name: string;
  test_input: string;
  expected_output: string;
  score_weight: number;
  is_public: boolean;
  time_limit?: number;
  memory_limit?: number;
  order_num?: number;
}

export interface HomeworkDetail {
  id: number;
  course_id: string;
  teacher_id: string;
  title: string;
  description: string;
  programming_language: string;
  max_score: number;
  deadline: string | null;
  allow_late_submit: number;
  status: number;
  feedback_visible: number;
  test_cases: TestCase[];
}

export interface Submission {
  id: number;
  student_id: string;
  student_name: string | null;
  submit_time: string;
  judge_time: string | null;
  status: number;
  status_cn: string;
  score: number | null;
  compile_error: string | null;
  ai_feedback: string | null;
}

export interface GradeBookRow {
  student_id: string;
  student_name: string | null;
  score: number | null;
  submit_count: number;
  judge_time: string | null;
}

// 互动
export interface Interaction {
  id: number;
  course_id: string;
  student_id: string | null;
  student_name: string | null;
  interaction_type: string;
  content: string;
  score: number | null;
  teacher_id: string;
  lesson_date: string;
  create_time: string;
}

export interface InteractionStats {
  course_id: string;
  total: number;
  enrolled_count: number;
  by_type: Record<string, number>;
  today_count: number;
  top_students: { student_id: string; name: string | null; count: number }[];
}

export interface RandomPickResult {
  student_no: string;
  name: string;
}

// 辅导员
export interface CounselorClass {
  class_id: string;
  class_name: string;
  grade: string;
  major: string;
  department: string;
  student_count: number;
}

export interface CounselorStudent {
  student_no: string;
  name: string;
  gender: number;
  phone: string | null;
  email: string | null;
  status: number;
  class_id: string;
}

export interface WarningRow {
  student_no: string;
  name: string;
  class_name: string | null;
  attendance_rate: number | null;
  absent_count: number;
  homework_avg: number | null;
  class_avg: number | null;
  reasons: string[];
}

export interface StudentProfile {
  student: {
    student_no: string;
    name: string;
    gender: number;
    phone: string | null;
    email: string | null;
    status: number;
    class_id: string;
    class_name: string | null;
  };
  attendance: {
    total: number;
    status_count: Record<string, number>;
    attendance_rate: number | null;
    recent: {
      id: number;
      course_id: string;
      course_name: string | null;
      attendance_date: string;
      status: number;
      status_cn: string;
      check_in_time: string | null;
    }[];
  };
  grades: {
    homework_id: number;
    homework_title: string | null;
    course_id: string;
    score: number | null;
    judge_time: string | null;
  }[];
  interactions: {
    id: number;
    course_id: string;
    interaction_type: string;
    content: string;
    score: number | null;
    lesson_date: string;
    create_time: string;
  }[];
}

export interface CounselorStat {
  class_count: number;
  student_total: number;
  avg_attendance_rate: number | null;
  warning_count: number;
}

export interface NotifyResult {
  sent: number;
}

// ============ 管理端 ============

export interface AdminOverview {
  student_count: number;
  teacher_count: number;
  counselor_count: number;
  admin_count: number;
  course_count: number;
  class_count: number;
  attendance_count: number;
  homework_count: number;
  submission_count: number;
  attendance_trend: { date: string; count: number }[];
}

export type AdminStat = AdminOverview;

export interface AdminUser {
  role: string;
  user_id: string;
  name: string;
  gender?: number;
  phone?: string | null;
  email?: string | null;
  status?: number;
  create_time?: string;
  class_id?: string;
  class_name?: string | null;
  department?: string | null;
  title?: string | null;
}

export interface AdminCourse {
  course_id: string;
  course_name: string;
  credit: number | null;
  hours: number | null;
  semester: string | null;
  teacher_id: string | null;
  teacher_name: string | null;
  status: number;
  student_count: number;
}

export interface AdminClass {
  class_id: string;
  class_name: string;
  grade: string | null;
  major: string | null;
  department: string | null;
  student_count: number;
}

export interface AdminEnrollment {
  id: number;
  course_id: string;
  course_name: string | null;
  student_no: string;
  student_name: string | null;
  status: number;
  create_time: string;
}

export interface AdminSchedule {
  id: number;
  course_id: string;
  course_name: string | null;
  class_id: string;
  class_name: string | null;
  weekday: number;
  start_time: string;
  end_time: string;
  weeks: string | null;
  classroom: string | null;
}

export interface AdminAudit {
  id: number;
  user_id: string;
  user_role: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: string | null;
  create_time: string;
}

// ============ AI 模块 ============

// AI 备课助手响应
export interface AiAssistResp {
  course_id: string;
  topic: string;
  content: string;
}

// 答疑热词
export interface AiHotword {
  word: string;
  count: number;
}

// AI 整作业批改结果
export interface AiGradeAllResp {
  graded: number;
  failed: number;
  degraded: number;
}

// AI 班级错误分析报告
export interface AiErrorReport {
  homework_id: number;
  homework_title: string;
  language: string;
  sample_count: number;
  submission_count: number;
  report: string; // markdown
}

// 知识库条目
export interface AiKnowledge {
  id: number;
  course_id: string | null;
  subject: string | null;
  title: string;
  content: string;
  difficulty: number;
  sort_order: number;
  status: number;
  create_time: string;
  update_time: string | null;
}

export interface AiKnowledgePayload {
  course_id: string;
  title: string;
  content?: string;
  subject?: string | null;
  difficulty?: number;
  sort_order?: number;
  status?: number;
}

// 评分规则
export interface AiRule {
  id: number;
  course_id: string | null;
  subject: string | null;
  name: string;
  content: string;
  rule_type: string; // score_point / deduct
  weight: number;
  max_score: number;
  criteria: string | null;
  sort_order: number;
  status: number;
  create_time: string;
  update_time: string | null;
}

export interface AiRulePayload {
  course_id?: string | null;
  name: string;
  content: string;
  subject?: string | null;
  rule_type?: string; // score_point / deduct
  weight?: number;
  max_score?: number;
  criteria?: string | null;
  sort_order?: number;
  status?: number;
}
