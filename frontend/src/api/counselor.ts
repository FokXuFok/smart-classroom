import http from './http';
import type {
  CounselorClass,
  CounselorStudent,
  WarningRow,
  StudentProfile,
  CounselorStat,
  NotifyResult,
} from './types';

export const counselorApi = {
  classes: () => http.get<CounselorClass[]>('/counselor/classes'),
  students: (classId: string) =>
    http.get<CounselorStudent[]>('/counselor/students', {
      params: { class_id: classId },
    }),
  warnings: () => http.get<WarningRow[]>('/counselor/warnings'),
  profile: (studentNo: string) =>
    http.get<StudentProfile>(`/counselor/student/${studentNo}/profile`),
  stat: () => http.get<CounselorStat>('/counselor/stat'),
  notify: (payload: {
    class_ids?: string[];
    student_nos?: string[];
    title: string;
    content: string;
  }) => http.post<NotifyResult>('/counselor/notify', payload),
};
