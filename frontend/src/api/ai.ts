// AI 模块接口:备课助手 / 答疑热词 / 整作业AI批改 / 班级错误分析 / 知识库CRUD / 评分规则CRUD
// 对齐后端 app/api/ai.py
import http from './http';
import type {
  AiAssistResp,
  AiHotword,
  AiKnowledge,
  AiKnowledgePayload,
  AiRule,
  AiRulePayload,
  AiGradeAllResp,
  AiErrorReport,
} from './types';

export const aiApi = {
  // 教师备课助手:输入主题,AI 生成备课内容
  teacherAssist: (payload: { course_id: string; topic: string }) =>
    http.post<AiAssistResp>('/ai/teacher/assist', payload),

  // 答疑热词:统计本课学生提问的高频词
  hotwords: (courseId: string) =>
    http.get<AiHotword[]>('/ai/qa/hotwords', { params: { course_id: courseId } }),

  // 整作业 AI 批量批改(对已评测提交生成 AI 反馈,失败降级规则反馈)
  gradeAll: (homeworkId: number) =>
    http.post<AiGradeAllResp>(`/ai/homework/${homeworkId}/grade-all`),

  // 班级错误分析 Agent:聚合错误样本生成「高频错误统计+讲评建议」
  analyzeErrors: (homeworkId: number) =>
    http.post<AiErrorReport>(`/ai/homework/${homeworkId}/analyze-errors`),

  // ---------- 知识库 CRUD ----------
  listKnowledge: (courseId?: string) =>
    http.get<AiKnowledge[]>('/ai/knowledge', {
      params: { course_id: courseId || undefined },
    }),
  createKnowledge: (payload: AiKnowledgePayload) =>
    http.post('/ai/knowledge', payload),
  updateKnowledge: (payload: AiKnowledgePayload & { id: number }) =>
    http.put('/ai/knowledge', payload),
  deleteKnowledge: (id: number) =>
    http.delete('/ai/knowledge', { params: { id } }),

  // ---------- 评分规则 CRUD ----------
  listRules: (courseId?: string) =>
    http.get<AiRule[]>('/ai/rules', {
      params: { course_id: courseId || undefined },
    }),
  createRule: (payload: AiRulePayload) =>
    http.post('/ai/rules', payload),
  updateRule: (payload: AiRulePayload & { id: number }) =>
    http.put('/ai/rules', payload),
  deleteRule: (id: number) => http.delete(`/ai/rules/${id}`),
};
