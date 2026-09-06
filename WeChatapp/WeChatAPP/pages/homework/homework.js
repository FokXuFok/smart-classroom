// pages/homework/homework.js
const { get } = require('../../utils/request')
const app = getApp()

Page({
  data: {
    homeworkList: [],
    loading: true,
  },

  onShow() {
    if (!app.checkLogin()) return
    this.loadList()
  },

  onPullDownRefresh() {
    this.loadList().finally(() => wx.stopPullDownRefresh())
  },

  async loadList() {
    this.setData({ loading: true })
    try {
      const list = await get('/api/student/homework/list')
      const names = app.globalData.courseNames || {}
      this.setData({
        homeworkList: (list || []).map((h) => ({
          ...h,
          course_name: names[h.course_id] || h.course_id,
          score_text:
            h.my_best_score === null || h.my_best_score === undefined
              ? '未完成'
              : `${h.my_best_score}/${h.max_score}`,
          deadline_text: h.deadline ? String(h.deadline).replace('T', ' ').substring(0, 16) : '无截止',
        })),
      })
    } catch (e) {
      // request 已提示
    } finally {
      this.setData({ loading: false })
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/homework-detail/homework-detail?id=${id}` })
  },
})
