// pages/notification/notification.js
const { get, post } = require('../../utils/request')
const app = getApp()

Page({
  data: {
    unreadCount: 0,
    items: [],
  },

  onShow() {
    if (!app.checkLogin()) return
    this.loadList()
  },

  onPullDownRefresh() {
    this.loadList().finally(() => wx.stopPullDownRefresh())
  },

  async loadList() {
    try {
      const data = await get('/api/notification/list?limit=50')
      this.setData({
        unreadCount: data.unread_count || 0,
        items: (data.items || []).map((n) => ({
          ...n,
          time_text: n.create_time ? String(n.create_time).replace('T', ' ').substring(0, 16) : '',
        })),
      })
    } catch (e) {
      // request 已提示
    }
  },

  async onReadAll() {
    try {
      await post('/api/notification/read-all')
      wx.showToast({ title: '已全部标记为已读', icon: 'success' })
      this.loadList()
    } catch (e) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' })
    }
  },

  async onItemTap(e) {
    const id = e.currentTarget.dataset.id
    const isRead = e.currentTarget.dataset.read
    if (!isRead) {
      try {
        await post(`/api/notification/read/${id}`)
        this.loadList()
      } catch (e) {
        // 静默
      }
    }
  },
})
