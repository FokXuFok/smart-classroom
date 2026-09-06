// app.js
const config = require('./config')

App({
  globalData: {
    // 当前登录用户信息
    userInfo: null,
    // 课程名称缓存 {course_id: course_name}
    courseNames: {},
  },

  onLaunch() {
    // 启动时恢复登录态
    const userInfo = wx.getStorageSync('userInfo')
    if (userInfo) {
      this.globalData.userInfo = userInfo
    }
  },

  /**
   * 检查登录态：未登录则跳转登录页
   * @returns {boolean} 是否已登录
   */
  checkLogin() {
    const userInfo = wx.getStorageSync('userInfo')
    if (!userInfo) {
      wx.reLaunch({ url: '/pages/login/login' })
      return false
    }
    this.globalData.userInfo = userInfo
    return true
  },

  /**
   * 设置登录用户信息
   */
  setUserInfo(info) {
    this.globalData.userInfo = info
    wx.setStorageSync('userInfo', info)
  },

  /**
   * 清除登录态
   */
  clearUserInfo() {
    this.globalData.userInfo = null
    wx.removeStorageSync('userInfo')
  },
})
