// pages/checkin/checkin.js
const { get, post } = require('../../utils/request')
const { chooseImageToBase64 } = require('../../utils/image')
const config = require('../../config')
const app = getApp()

Page({
  data: {
    activeSessions: [],
    selectedSessionId: null,
    selectedSession: null,
    remainingText: '',
    history: [],
    submitting: false,
    registering: false,
    showApply: false,
    applyReason: '',
    applySessionId: null,
  },

  _timer: null,

  onShow() {
    if (!app.checkLogin()) return
    this.loadData()
  },

  onHide() {
    this._clearTimer()
  },

  onUnload() {
    this._clearTimer()
  },

  onPullDownRefresh() {
    this.loadData().finally(() => wx.stopPullDownRefresh())
  },

  _clearTimer() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },

  _startCountdown() {
    this._clearTimer()
    if (!this.data.selectedSession) return
    let remaining = this.data.selectedSession.remaining_seconds || 0
    const update = () => {
      if (remaining <= 0) {
        this.setData({ remainingText: '已结束' })
        this._clearTimer()
        return
      }
      const min = Math.floor(remaining / 60)
      const sec = remaining % 60
      this.setData({
        remainingText: `${min}:${sec < 10 ? '0' : ''}${sec}`,
      })
      remaining--
    }
    update()
    this._timer = setInterval(update, 1000)
  },

  async loadData() {
    try {
      const [active, history] = await Promise.all([
        get('/api/student/checkin/active').catch(() => []),
        get('/api/student/checkin/history').catch(() => []),
      ])
      const names = app.globalData.courseNames || {}
      const sessions = (active || []).map((s) => ({
        ...s,
        course_name: names[s.course_id] || s.course_id,
      }))
      this.setData({
        activeSessions: sessions,
        selectedSessionId: sessions.length ? sessions[0].id : null,
        selectedSession: sessions.length ? sessions[0] : null,
        history: (history || []).map((r) => ({
          ...r,
          course_name: names[r.course_id] || r.course_id,
        })),
      })
      this._startCountdown()
    } catch (e) {
      // request 已统一提示
    }
  },

  onSessionChange(e) {
    const idx = Number(e.detail.value)
    const s = this.data.activeSessions[idx]
    this.setData({ selectedSessionId: s.id, selectedSession: s })
    this._startCountdown()
  },

  async onFaceRegister() {
    try {
      const imageB64 = await chooseImageToBase64(true)
      this.setData({ registering: true })
      await post('/api/student/face/register', { image_b64: imageB64 })
      wx.showModal({
        title: '注册成功',
        content: '人脸模板已保存，现在可以使用摄像头签到',
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

  async onCameraCheckin() {
    const { selectedSessionId, selectedSession } = this.data
    if (!selectedSessionId) {
      wx.showToast({ title: '暂无进行中的签到', icon: 'none' })
      return
    }
    try {
      const f1 = await chooseImageToBase64(true)
      this.setData({ submitting: true })

      let lat = selectedSession.teacher_lat
      let lng = selectedSession.teacher_lng
      try {
        const loc = await new Promise((resolve, reject) => {
          wx.getLocation({
            type: 'gcj02',
            isHighAccuracy: true,
            success: resolve,
            fail: reject,
          })
        })
        lat = loc.latitude
        lng = loc.longitude
      } catch (e) {
        wx.showToast({ title: '定位失败，使用教师坐标', icon: 'none' })
      }

      let f2 = null
      try {
        wx.showLoading({ title: '请再拍一张（活体）', mask: true })
        f2 = await chooseImageToBase64(true)
        wx.hideLoading()
      } catch (e) {
        wx.hideLoading()
      }

      const data = await post('/api/student/checkin/submit', {
        session_id: selectedSessionId,
        image_b64: f1,
        image_b64_2: f2,
        lat,
        lng,
      })
      wx.showModal({
        title: '签到成功',
        content: `${data.status_cn} · 相似度 ${data.similarity} · 距离 ${data.distance_m} 米`,
        showCancel: false,
        success: () => this.loadData(),
      })
    } catch (e) {
      if (!e.cancelled) {
        wx.showToast({ title: e.message || '签到失败', icon: 'none', duration: 3000 })
      }
    } finally {
      this.setData({ submitting: false })
    }
  },

  async onDemoCheckin() {
    const { selectedSessionId, selectedSession } = this.data
    if (!selectedSessionId) {
      wx.showToast({ title: '暂无进行中的签到', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    try {
      const lat = selectedSession ? selectedSession.teacher_lat : config.DEMO_LAT
      const lng = selectedSession ? selectedSession.teacher_lng : config.DEMO_LNG
      const data = await post('/api/student/checkin/submit', {
        session_id: selectedSessionId,
        image_b64: 'demo',
        lat,
        lng,
      })
      wx.showModal({
        title: '签到成功（演示）',
        content: `${data.status_cn} · 相似度 ${data.similarity} · 距离 ${data.distance_m} 米`,
        showCancel: false,
        success: () => this.loadData(),
      })
    } catch (e) {
      wx.showToast({ title: e.message || '签到失败', icon: 'none', duration: 3000 })
    } finally {
      this.setData({ submitting: false })
    }
  },

  onOpenApply(e) {
    const sid = e.currentTarget.dataset.id
    this.setData({ showApply: true, applySessionId: sid, applyReason: '' })
  },

  onApplyReasonInput(e) {
    this.setData({ applyReason: e.detail.value })
  },

  onCancelApply() {
    this.setData({ showApply: false, applyReason: '', applySessionId: null })
  },

  async onSubmitApply() {
    const { applySessionId, applyReason } = this.data
    if (!applyReason.trim()) {
      wx.showToast({ title: '请填写请假理由', icon: 'none' })
      return
    }
    try {
      await post('/api/student/checkin/apply', {
        session_id: applySessionId,
        reason: applyReason.trim(),
      })
      wx.showToast({ title: '申请已提交，待教师审核', icon: 'success' })
      this.setData({ showApply: false, applyReason: '', applySessionId: null })
      this.loadData()
    } catch (e) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
    }
  },
})
