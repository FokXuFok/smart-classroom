// pages/ai/ai.js
const { get, post } = require('../../utils/request')
const app = getApp()

Page({
  data: {
    courses: [],
    courseIndex: 0,
    selectedCourseId: '',
    question: '',
    answer: '',
    asking: false,
    history: [],
  },

  onShow() {
    if (!app.checkLogin()) return
    this.loadCourses()
  },

  async loadCourses() {
    try {
      const list = await get('/api/student/courses')
      const courses = list || []
      this.setData({
        courses,
        selectedCourseId: courses.length ? courses[0].course_id : '',
      })
    } catch (e) {
      // request 已提示
    }
  },

  onCourseChange(e) {
    const idx = Number(e.detail.value)
    this.setData({
      courseIndex: idx,
      selectedCourseId: this.data.courses[idx].course_id,
    })
  },

  onQuestionInput(e) {
    this.setData({ question: e.detail.value })
  },

  async onAsk() {
    const { question, selectedCourseId } = this.data
    if (!question.trim()) {
      wx.showToast({ title: '请输入问题', icon: 'none' })
      return
    }
    if (!selectedCourseId) {
      wx.showToast({ title: '请选择课程', icon: 'none' })
      return
    }
    this.setData({ asking: true, answer: 'AI 助教正在思考中…' })
    try {
      const data = await post('/api/ai/qa', {
        course_id: selectedCourseId,
        question: question.trim(),
        is_anonymous: true,
      })
      this.setData({ answer: data.answer || '（空回答）' })
      this.loadHistory()
    } catch (e) {
      this.setData({ answer: '回答失败：' + (e.message || '请稍后重试') })
    } finally {
      this.setData({ asking: false })
    }
  },

  async loadHistory() {
    try {
      const list = await get(`/api/ai/qa/history?course_id=${this.data.selectedCourseId}&limit=10`)
      this.setData({ history: list || [] })
    } catch (e) {
      // 静默
    }
  },
})
