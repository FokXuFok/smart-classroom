// pages/login/login.js
const { post } = require('../../utils/request')
const { detectServer } = require('../../utils/server')
const config = require('../../config')
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
    // 服务器设置
    showServer: false,
    currentServer: '',
    serverInput: '',
    detecting: false,
    detectMsg: '',
  },

  onLoad() {
    // 已登录则直接进入首页
    if (wx.getStorageSync('userInfo')) {
      wx.switchTab({ url: '/pages/index/index' })
    }
    // 显示当前生效的服务器地址
    const base = config.API_BASE
    this.setData({ currentServer: base, serverInput: base })
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value })
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value })
  },

  // ---------- 服务器设置 ----------
  onToggleServer() {
    this.setData({ showServer: !this.data.showServer })
  },

  onServerInput(e) {
    this.setData({ serverInput: e.detail.value })
  },

  onSaveServer() {
    const url = (this.data.serverInput || '').trim().replace(/\/+$/, '')
    if (!/^https?:\/\/[\d.A-Za-z-]+(:\d+)?$/.test(url)) {
      wx.showModal({
        title: '地址格式不对',
        content: '请输入完整地址，例如 http://10.90.193.20:8080',
        showCancel: false,
      })
      return
    }
    config.setApiBase(url)
    this.setData({ currentServer: url, detectMsg: '✅ 已保存：' + url })
    wx.showToast({ title: '服务器地址已保存', icon: 'success' })
  },

  async onAutoDetect() {
    this.setData({ detecting: true, detectMsg: '正在检测可用服务器…' })
    try {
      const found = await detectServer({
        onProgress: (i, total, url) => {
          this.setData({ detectMsg: '正在检测 ' + i + '/' + total + '：' + url })
        },
      })
      if (found) {
        this.setData({
          currentServer: found,
          serverInput: found,
          detectMsg: '✅ 已找到服务器：' + found,
        })
      } else {
        this.setData({ detectMsg: '❌ 未找到可用服务器，请检查后端是否启动、手机与电脑是否同一网络' })
      }
    } catch (e) {
      this.setData({ detectMsg: '❌ 检测异常：' + (e && e.message ? e.message : '未知错误') })
    } finally {
      this.setData({ detecting: false })
    }
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
      // 用模态框显示完整错误（toast 会截断长文本）
      wx.showModal({
        title: '登录失败',
        content: e.message || '登录失败',
        showCancel: false,
      })
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
