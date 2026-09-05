import http from './http';
import type {
  Homework,
  HomeworkDetail,
  Submission,
  GradeBookRow,
  TestCase,
} from './types';

export interface HomeworkPayload {
  course_id: string;
  title: string;
  description?: string;
  programming_language?: string;
  max_score?: number;
  deadline?: string | null;
  allow_late_submit?: boolean;
  test_cases?: TestCase[];
  status?: number;
}

export const homeworkApi = {
  list: (courseId?: string) =>
    http.get<Homework[]>('/homework/list', {
      params: { course_id: courseId || undefined },
    }),
  detail: (id: number) => http.get<HomeworkDetail>(`/homework/${id}`),
  create: (payload: HomeworkPayload) => http.post('/homework/', payload),
  update: (id: number, payload: HomeworkPayload) =>
    http.put(`/homework/${id}`, payload),
  delete: (id: number) => http.delete(`/homework/${id}`),
  submissions: (id: number) =>
    http.get<Submission[]>(`/homework/${id}/submissions`),
  gradebook: (id: number) =>
    http.get<GradeBookRow[]>(`/homework/${id}/gradebook`),
  gradebookExportUrl: (id: number) =>
    `${import.meta.env.VITE_API_BASE}/homework/${id}/gradebook/export`,
  similarity: (id: number) => http.post(`/homework/${id}/similarity`),
  rejudge: (id: number) => http.post(`/homework/${id}/rejudge`),
  openFeedback: (id: number) => http.post(`/homework/${id}/open-feedback`),
};
