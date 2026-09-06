// pages/login/login.js
const { post } = require('../../utils/request')
const app = getApp()

Page({
  data: {
    username: '',
    password: '',
    loading: false,
    showRegister: false,
    // 注册表单
    regName: '',
    regUsername: '',
    regPassword: '',
    regClassId: '',
    classOptions: [],
    classIndex: -1,
  },

  onLoad() {
    // 已登录则直接进入首页
    if (wx.getStorageSync('userInfo')) {
      wx.switchTab({ url: '/pages/index/index' })
    }
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value })
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value })
  },

  async onLogin() {
    const { username, password } = this.data
    if (!username.trim()) {
      wx.showToast({ title: '请输入学号', icon: 'none' })
      return
    }
    if (!password) {
      wx.showToast({ title: '请输入密码', icon: 'none' })
      return
    }

    this.setData({ loading: true })
    try {
      const data = await post('/api/auth/login', {
        username: username.trim(),
        password,
      })
      const info = {
        role: data.role,
        name: data.name,
        user_id: data.user_id,
      }
      app.setUserInfo(info)
      wx.showToast({ title: '登录成功', icon: 'success' })
      setTimeout(() => {
        wx.switchTab({ url: '/pages/index/index' })
      }, 500)
    } catch (e) {
      wx.showToast({ title: e.message || '登录失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  // ---------- 注册 ----------
  async onShowRegister() {
    this.setData({ showRegister: true })
    // 加载班级列表
    try {
      const { get } = require('../../utils/request')
      const list = await get('/api/auth/class-options', { silent: true })
      this.setData({ classOptions: list || [] })
    } catch (e) {
      // 班级列表加载失败不阻塞注册
    }
  },

  onCancelRegister() {
    this.setData({ showRegister: false })
  },

  onClassChange(e) {
    const idx = Number(e.detail.value)
    this.setData({
      classIndex: idx,
      regClassId: this.data.classOptions[idx].class_code,
    })
  },

  onRegNameInput(e) { this.setData({ regName: e.detail.value }) },
  onRegUsernameInput(e) { this.setData({ regUsername: e.detail.value }) },
  onRegPasswordInput(e) { this.setData({ regPassword: e.detail.value }) },

  async onRegister() {
    const { regName, regUsername, regPassword, regClassId } = this.data
    if (!regName.trim()) { wx.showToast({ title: '请输入姓名', icon: 'none' }); return }
    if (!regUsername.trim()) { wx.showToast({ title: '请输入学号', icon: 'none' }); return }
    if (!regPassword || regPassword.length < 6) {
      wx.showToast({ title: '密码至少6位', icon: 'none' }); return
    }
    if (!regClassId) { wx.showToast({ title: '请选择班级', icon: 'none' }); return }

    this.setData({ loading: true })
    try {
      await post('/api/auth/register', {
        username: regUsername.trim(),
        name: regName.trim(),
        password: regPassword,
        role: 'student',
        class_id: regClassId,
      })
      wx.showModal({
        title: '注册成功',
        content: '请等待管理员审核通过后登录',
        showCancel: false,
        success: () => {
          this.setData({ showRegister: false, loading: false })
        },
      })
    } catch (e) {
      wx.showToast({ title: e.message || '注册失败', icon: 'none' })
      this.setData({ loading: false })
    }
  },
})
