import type { RouteRecordRaw } from 'vue-router';

// 路由表:登录 / 404 / teacher / counselor / admin 各 children
// 菜单从 meta.menu 派生(见 menus.ts),避免菜单与路由不同步
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: () => {
      try {
        const raw = sessionStorage.getItem('sc-auth');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed.role) return `/${parsed.role}`;
        }
      } catch {
        /* ignore */
      }
      return '/login';
    },
  },
  {
    path: '/login',
    component: () => import('@/layouts/BlankLayout.vue'),
    children: [
      { path: '', component: () => import('@/views/auth/Login.vue') },
    ],
    meta: { public: true, title: '登录' },
  },
  {
    path: '/teacher',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requireRole: 'teacher' },
    children: [
      { path: '', redirect: '/teacher/overview' },
      {
        path: 'overview',
        component: () => import('@/views/teacher/TeacherOverview.vue'),
        meta: { title: '总览', menu: { icon: 'DataAnalysis', order: 1 } },
      },
      {
        path: 'checkin',
        component: () => import('@/views/teacher/TeacherCheckin.vue'),
        meta: { title: '课堂签到', menu: { icon: 'EditPen', order: 2 } },
      },
      {
        path: 'checkin/:sessionId',
        component: () => import('@/views/teacher/CheckinDashboard.vue'),
        meta: { title: '签到看板', hideInMenu: true },
      },
      {
        path: 'review',
        component: () => import('@/views/teacher/CheckinReview.vue'),
        meta: { title: '待复核审核', menu: { icon: 'CircleCheck', order: 3 } },
      },
      {
        path: 'export',
        component: () => import('@/views/teacher/CheckinExport.vue'),
        meta: { title: '考勤导出', menu: { icon: 'Download', order: 4 } },
      },
      {
        path: 'homework',
        component: () => import('@/views/teacher/HomeworkList.vue'),
        meta: { title: '作业管理', menu: { icon: 'Document', order: 5 } },
      },
      {
        path: 'homework/:id',
        component: () => import('@/views/teacher/HomeworkEdit.vue'),
        meta: { title: '作业编辑', hideInMenu: true },
      },
      {
        path: 'courses',
        component: () => import('@/views/teacher/TeacherCourses.vue'),
        meta: { title: '我的课程', menu: { icon: 'Reading', order: 6 } },
      },
      {
        path: 'students',
        component: () => import('@/views/teacher/TeacherStudents.vue'),
        meta: { title: '学生管理', menu: { icon: 'User', order: 7 } },
      },
      {
        path: 'interact',
        component: () => import('@/views/teacher/TeacherInteract.vue'),
        meta: { title: '点名互动', menu: { icon: 'ChatDotRound', order: 8 } },
      },
    ],
  },
  {
    path: '/counselor',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requireRole: 'counselor' },
    children: [
      { path: '', redirect: '/counselor/overview' },
      {
        path: 'overview',
        component: () => import('@/views/counselor/CounselorOverview.vue'),
        meta: { title: '总览预警', menu: { icon: 'DataAnalysis', order: 1 } },
      },
      {
        path: 'warnings',
        component: () => import('@/views/counselor/CounselorWarnings.vue'),
        meta: { title: '预警学生', menu: { icon: 'Warning', order: 2 } },
      },
      {
        path: 'students',
        component: () => import('@/views/counselor/CounselorStudents.vue'),
        meta: { title: '学生档案', menu: { icon: 'User', order: 3 } },
      },
      {
        path: 'classes',
        component: () => import('@/views/counselor/CounselorClasses.vue'),
        meta: { title: '班级概览', menu: { icon: 'School', order: 4 } },
      },
      {
        path: 'attendance',
        component: () => import('@/views/counselor/CounselorAttendance.vue'),
        meta: { title: '出勤率图表', menu: { icon: 'TrendCharts', order: 5 } },
      },
      {
        path: 'notify',
        component: () => import('@/views/counselor/CounselorNotify.vue'),
        meta: { title: '群发通知', menu: { icon: 'Promotion', order: 6 } },
      },
      {
        path: 'batch',
        component: () => import('@/views/counselor/CounselorBatch.vue'),
        meta: { title: '批量提醒', menu: { icon: 'BellFilled', order: 7 } },
      },
    ],
  },
  {
    path: '/admin',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requireRole: 'admin' },
    children: [
      { path: '', redirect: '/admin/overview' },
      {
        path: 'overview',
        component: () => import('@/views/admin/AdminOverview.vue'),
        meta: { title: '数据看板', menu: { icon: 'board', order: 1 } },
      },
      {
        path: 'users',
        component: () => import('@/views/admin/AdminUsers.vue'),
        meta: { title: '人员管理', menu: { icon: 'User', order: 2 } },
      },
      {
        path: 'courses',
        component: () => import('@/views/admin/AdminCourses.vue'),
        meta: { title: '课程管理', menu: { icon: 'Reading', order: 3 } },
      },
      {
        path: 'classes',
        component: () => import('@/views/admin/AdminClasses.vue'),
        meta: { title: '班级管理', menu: { icon: 'School', order: 4 } },
      },
      {
        path: 'enrollments',
        component: () => import('@/views/admin/AdminEnrollments.vue'),
        meta: { title: '选课管理', menu: { icon: 'Connection', order: 5 } },
      },
      {
        path: 'schedules',
        component: () => import('@/views/admin/AdminSchedules.vue'),
        meta: { title: '课表管理', menu: { icon: 'Calendar', order: 6 } },
      },
      {
        path: 'audit',
        component: () => import('@/views/admin/AdminAudit.vue'),
        meta: { title: '审计日志', menu: { icon: 'List', order: 7 } },
      },
      {
        path: 'stats',
        component: () => import('@/views/admin/AdminStats.vue'),
        meta: { title: '数据统计', menu: { icon: 'TrendCharts', order: 8 } },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    component: () => import('@/views/error/NotFound.vue'),
    meta: { public: true, title: '页面不存在' },
  },
];
