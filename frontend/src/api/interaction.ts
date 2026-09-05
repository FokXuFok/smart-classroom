import http from './http';
import type {
  Interaction,
  InteractionStats,
  RandomPickResult,
} from './types';

export interface InteractionPayload {
  course_id: string;
  student_id?: string;
  interaction_type: 'question' | 'rating' | 'random_pick';
  content?: string;
  score?: number;
  lesson_date?: string;
}

export const interactionApi = {
  create: (payload: InteractionPayload) =>
    http.post<Interaction>('/interaction/', payload),
  list: (params: {
    course_id?: string;
    date?: string;
    student_id?: string;
  }) => http.get<Interaction[]>('/interaction/list', { params }),
  randomPick: (courseId: string) =>
    http.get<RandomPickResult>(`/interaction/random-pick/${courseId}`),
  stats: (courseId: string) =>
    http.get<InteractionStats>(`/interaction/stats/${courseId}`),
};
