// pages/index/index.js
const { get } = require('../../utils/request')
const app = getApp()

// 课程图标配色池
const ICON_POOL = [
  { bg: 'linear-gradient(135deg,#6366f1,#8b5cf6)', text: '📘' },
  { bg: 'linear-gradient(135deg,#10b981,#34d399)', text: '📗' },
  { bg: 'linear-gradient(135deg,#f59e0b,#fbbf24)', text: '📙' },
  { bg: 'linear-gradient(135deg,#ef4444,#f87171)', text: '📕' },
  { bg: 'linear-gradient(135deg,#3b82f6,#60a5fa)', text: '📘' },
  { bg: 'linear-gradient(135deg,#8b5cf6,#a78bfa)', text: '📗' },
]

Page({
  data: {
    userInfo: null,
    stats: { total: 0, detail: {} },
    courses: [],
    activeSessions: [],
    unreadCount: 0,
    loading: true,
  },

  onShow() {
    if (!app.checkLogin()) return
    this.setData({ userInfo: app.globalData.userInfo })
    this.loadAll()
  },

  onPullDownRefresh() {
    this.loadAll().finally(() => wx.stopPullDownRefresh())
  },

  async loadAll() {
    this.setData({ loading: true })
    try {
      const [stats, courses, active, notif] = await Promise.all([
        get('/api/student/attendance/stats').catch(() => ({ total: 0, detail: {} })),
        get('/api/student/courses').catch(() => []),
        get('/api/student/checkin/active').catch(() => []),
        get('/api/notification/list?limit=1', { silent: true }).catch(() => ({ unread_count: 0 })),
      ])
      const names = {}
      ;(courses || []).forEach((c) => { names[c.course_id] = c.course_name })
      app.globalData.courseNames = Object.assign(app.globalData.courseNames, names)

      // 为课程分配图标配色 + 预算出勤百分比（WXML 不支持 .toFixed() 方法调用）
      const enriched = (courses || []).map((c, i) => {
        const icon = ICON_POOL[i % ICON_POOL.length]
        const pct = c.attendance_rate ? Math.floor(c.attendance_rate * 100) : 0
        return { ...c, bgColor: icon.bg, iconText: icon.text, attendance_pct: pct }
      })

      this.setData({
        stats: stats || { total: 0, detail: {} },
        courses: enriched,
        activeSessions: active || [],
        unreadCount: (notif && notif.unread_count) || 0,
      })
    } catch (e) {
      // 错误已由 request 统一提示
    } finally {
      this.setData({ loading: false })
    }
  },

  goCheckin() {
    wx.switchTab({ url: '/pages/checkin/checkin' })
  },

  goHomework() {
    wx.switchTab({ url: '/pages/homework/homework' })
  },

  goNotification() {
    wx.navigateTo({ url: '/pages/notification/notification' })
  },
})
