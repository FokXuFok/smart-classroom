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
    // 三重签到进度
    faceChecked: false,       // 人脸已采集
    geoChecked: false,        // 定位已采集
    fingerprintChecked: false, // 指纹已通过
    faceImg: null,            // 第一帧 base64
    faceImg2: null,           // 第二帧 base64（活体）
    lat: null,
    lng: null,
    fingerprintData: null,   // 指纹数据 "<json>|<sig>"
    stepStatus: '',          // 当前流程提示
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
      this._resetThreeFactor() // 切换会话时重置三重因子
    } catch (e) {
      // request 已统一提示
    }
  },

  // 切换会话或开始新一轮签到时重置
  _resetThreeFactor() {
    this.setData({
      faceChecked: false,
      geoChecked: false,
      fingerprintChecked: false,
      faceImg: null,
      faceImg2: null,
      lat: null,
      lng: null,
      fingerprintData: null,
      stepStatus: '',
    })
  },

  onSessionChange(e) {
    const idx = Number(e.detail.value)
    const s = this.data.activeSessions[idx]
    this.setData({ selectedSessionId: s.id, selectedSession: s })
    this._startCountdown()
    this._resetThreeFactor()
  },

  // ============ 三重签到：人脸采集 ============
  async onCaptureFace() {
    try {
      const img = await chooseImageToBase64(true)
      this.setData({
        faceImg: img,
        faceChecked: true,
        stepStatus: '✅ 人脸已采集，请继续定位',
      })
    } catch (e) {
      if (!e.cancelled) {
        wx.showToast({ title: e.message || '拍照失败', icon: 'none' })
      }
    }
  },

  // ============ 三重签到：定位采集 ============
  async onCaptureGeo() {
    const { selectedSession } = this.data
    try {
      this.setData({ stepStatus: '正在获取定位…' })
      const loc = await new Promise((resolve, reject) => {
        wx.getLocation({
          type: 'gcj02',
          isHighAccuracy: true,
          success: resolve,
          fail: reject,
        })
      })
      this.setData({
        lat: loc.latitude,
        lng: loc.longitude,
        geoChecked: true,
        stepStatus: `✅ 定位成功：${loc.latitude.toFixed(5)}, ${loc.longitude.toFixed(5)}`,
      })
    } catch (e) {
      // 定位失败时回退教师坐标，允许继续签到（围栏校验由后端做）
      if (selectedSession) {
        this.setData({
          lat: selectedSession.teacher_lat,
          lng: selectedSession.teacher_lng,
          geoChecked: true,
          stepStatus: '⚠️ 定位失败，使用教师坐标（围栏校验由后端判定）',
        })
      } else {
        this.setData({ stepStatus: '❌ 定位失败，请检查权限' })
      }
    }
  },

  // ============ 三重签到：指纹采集（微信 SOTER） ============
  async onCaptureFingerprint() {
    this.setData({ stepStatus: '正在唤起指纹…' })
    try {
      // 1) 检查设备是否支持 SOTER 生物认证
      const support = await new Promise((resolve, reject) => {
        wx.checkIsSupportSoterAuthentication({
          success: resolve,
          fail: reject,
        })
      })
      const modes = support.supportMode || []
      if (!modes.includes('fingerPrint')) {
        // 设备不支持指纹 → 直接标记通过（后端会接受 fingerprint=null 但记录为"设备不支持"）
        this.setData({
          fingerprintChecked: true,
          fingerprintData: null,
          stepStatus: '⚠️ 设备不支持指纹，跳过指纹因子',
        })
        return
      }

      // 2) 检查是否录入了指纹
      const enrolled = await new Promise((resolve, reject) => {
        wx.checkIsSoterEnrolledInDevice({
          checkAuthMode: 'fingerPrint',
          success: resolve,
          fail: reject,
        })
      })
      if (!enrolled.isEnrolled) {
        this.setData({
          stepStatus: '❌ 设备未录入指纹，请在系统设置中添加指纹后重试',
        })
        return
      }

      // 3) 启动指纹认证（弹出系统指纹弹窗）
      const authRes = await new Promise((resolve, reject) => {
        wx.startSoterAuthentication({
          requestAuthModes: ['fingerPrint'],
          challenge: `smartclass-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          authContent: '智慧课堂签到指纹验证',
          success: resolve,
          fail: reject,
        })
      })
      // authRes: { resultJSON, resultJSONSignature, errMsg }
      const fpData = `${authRes.resultJSON}|${authRes.resultJSONSignature}`
      this.setData({
        fingerprintChecked: true,
        fingerprintData: fpData,
        stepStatus: '✅ 指纹验证通过',
      })
    } catch (e) {
      const errMsg = (e && e.errMsg) || ''
      if (errMsg.includes('cancel')) {
        this.setData({ stepStatus: '❌ 用户取消了指纹验证' })
      } else {
        this.setData({
          stepStatus: `❌ 指纹验证失败：${errMsg || '未知'}`,
        })
      }
    }
  },

  // ============ 三重签到：提交 ============
  async onThreeFactorSubmit() {
    const {
      selectedSessionId, faceImg, faceImg2, lat, lng,
      fingerprintData, faceChecked, geoChecked, fingerprintChecked,
    } = this.data
    if (!selectedSessionId) {
      wx.showToast({ title: '暂无进行中的签到', icon: 'none' })
      return
    }
    // 三重因子齐全校验
    if (!faceChecked) {
      wx.showToast({ title: '请先采集人脸', icon: 'none' })
      return
    }
    if (!geoChecked) {
      wx.showToast({ title: '请先采集定位', icon: 'none' })
      return
    }
    if (!fingerprintChecked) {
      wx.showToast({ title: '请先验证指纹', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    try {
      const data = await post('/api/student/checkin/submit', {
        session_id: selectedSessionId,
        image_b64: faceImg,
        image_b64_2: faceImg2,
        lat,
        lng,
        fingerprint: fingerprintData,
      })
      wx.showModal({
        title: '签到成功',
        content: `${data.status_cn} · 相似度 ${data.similarity} · 距离 ${data.distance_m} 米`,
        showCancel: false,
        success: () => {
          this._resetThreeFactor()
          this.loadData()
        },
      })
    } catch (e) {
      wx.showToast({ title: e.message || '签到失败', icon: 'none', duration: 3000 })
    } finally {
      this.setData({ submitting: false })
    }
  },

  // ============ 演示签到（跳过人脸/指纹） ============
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
      wx.showToast({ title: e.message || '签到失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },

  // ============ 第二帧（活体，可选） ============
  async onCaptureLive() {
    try {
      const img2 = await chooseImageToBase64(true)
      this.setData({
        faceImg2: img2,
        stepStatus: '✅ 已采集第二帧（活体检测）',
      })
    } catch (e) {
      if (!e.cancelled) {
        wx.showToast({ title: e.message || '拍照失败', icon: 'none' })
      }
    }
  },

  // ============ 人脸注册 ============
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

  // ============ 请假/补签 ============
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
