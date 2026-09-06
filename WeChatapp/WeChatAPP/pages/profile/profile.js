// pages/profile/profile.js
const { post } = require('../../utils/request')
const { chooseImageToBase64 } = require('../../utils/image')
const app = getApp()

Page({
  data: {
    userInfo: null,
    registering: false,
  },

  onShow() {
    if (!app.checkLogin()) return
    this.setData({ userInfo: app.globalData.userInfo })
  },

  goInteract() {
    wx.navigateTo({ url: '/pages/interact/interact' })
  },

  goNotification() {
    wx.navigateTo({ url: '/pages/notification/notification' })
  },

  goCheckin() {
    wx.switchTab({ url: '/pages/checkin/checkin' })
  },

  async onFaceRegister() {
    try {
      const imageB64 = await chooseImageToBase64(true)
      this.setData({ registering: true })
      await post('/api/student/face/register', { image_b64: imageB64 })
      wx.showModal({
        title: '注册成功',
        content: '人脸模板已保存',
        showCancel: false,
      })
    } catch (e) {
      if (!e.cancelled) {
        wx.showToast({ title: e.message || '注册失败', icon: 'none' })
      }
    } finally {
      this.setData({ registering: false })
    }
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      success: async (res) => {
        if (res.confirm) {
          try {
            await post('/api/auth/logout')
          } catch (e) {
            // 忽略
          }
          app.clearUserInfo()
          wx.reLaunch({ url: '/pages/login/login' })
        }
      },
    })
  },
})
