// pages/interact/interact.js
const { get } = require('../../utils/request')
const app = getApp()

const TYPE_MAP = { question: '提问', rating: '评分', random_pick: '随机点名' }

Page({
  data: {
    list: [],
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
      const list = await get('/api/interaction/my')
      const names = app.globalData.courseNames || {}
      this.setData({
        list: (list || []).map((r) => ({
          ...r,
          course_name: names[r.course_id] || r.course_id,
          type_text: TYPE_MAP[r.interaction_type] || r.interaction_type,
          type_color:
            r.interaction_type === 'question'
              ? '#3b82f6'
              : r.interaction_type === 'rating'
              ? '#f59e0b'
              : '#8b5cf6',
        })),
      })
    } catch (e) {
      // request 已提示
    } finally {
      this.setData({ loading: false })
    }
  },
})
