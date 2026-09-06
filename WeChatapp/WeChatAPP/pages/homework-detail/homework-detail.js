// pages/homework-detail/homework-detail.js
const { get, post } = require('../../utils/request')
const app = getApp()

Page({
  data: {
    homeworkId: null,
    hw: null,
    code: '',
    submitting: false,
    submissions: [],
    showHistory: false,
  },

  onLoad(options) {
    if (!app.checkLogin()) return
    this.setData({ homeworkId: Number(options.id) })
    this.loadDetail()
  },

  async loadDetail() {
    try {
      const [hw, submissions] = await Promise.all([
        get(`/api/student/homework/${this.data.homeworkId}`),
        get(`/api/student/homework/${this.data.homeworkId}/my`).catch(() => []),
      ])
      const names = app.globalData.courseNames || {}
      this.setData({
        hw: {
          ...hw,
          course_name: names[hw.course_id] || hw.course_id,
          deadline_text: hw.deadline
            ? String(hw.deadline).replace('T', ' ').substring(0, 16)
            : '无截止',
        },
        submissions: submissions || [],
      })
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' })
    }
  },

  onCodeInput(e) {
    this.setData({ code: e.detail.value })
  },

  async onSubmit() {
    const { code, hw } = this.data
    if (!code.trim()) {
      wx.showToast({ title: '请输入代码', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    try {
      await post(`/api/student/homework/${this.data.homeworkId}/submit`, {
        code,
        language: hw.programming_language || 'python',
      })
      wx.showToast({ title: '提交成功，正在评测', icon: 'success' })
      this.setData({ showHistory: true })
      // 延迟刷新提交记录
      setTimeout(() => this.loadDetail(), 1500)
    } catch (e) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none', duration: 3000 })
    } finally {
      this.setData({ submitting: false })
    }
  },

  toggleHistory() {
    this.setData({ showHistory: !this.data.showHistory })
  },
})
