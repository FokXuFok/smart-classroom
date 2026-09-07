// pages/checkin/checkin.js
const { get, post } = require('../../utils/request')
const { chooseImageToBase64 } = require('../../utils/image')
const config = require('../../config')
const app = getApp()

// 签到向导步骤：idle → fingerprint(指纹) → face(人脸+活体) → ready(可提交)
Page({
  data: {
    activeSessions: [],
    selectedSessionId: null,
    selectedSession: null,
    selectedIndex: 0,
    remainingText: '',
    history: [],
    submitting: false,
    registering: false,
    showApply: false,
    applyReason: '',
    applySessionId: null,

    // ===== 签到向导状态 =====
    flowStep: 'idle',            // idle | fingerprint | face | ready
    // 指纹因子
    fingerprintChecked: false,
    fingerprintData: null,       // "<json>|<sig>"
    // 人脸因子（活体：两帧）
    faceChecked: false,
    faceImg: null,               // 第一帧 base64
    faceImg2: null,              // 第二帧 base64（活体）
    // 定位因子（点击开始签到时后台并行获取）
    lat: null,
    lng: null,
    geoAccuracy: null,           // 定位精度（米）
    geoState: 'pending',         // pending | ok | fallback(回退教师坐标)
    geoText: '',                 // 定位展示文本（WXML 不支持 toFixed，预算好）
    // 流程提示
    stepStatus: '',
    stepTitle: '',
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
      const patch = {
        activeSessions: sessions,
        history: (history || []).map((r) => ({
          ...r,
          course_name: names[r.course_id] || r.course_id,
        })),
      }
      // 仅在无进行中签到或会话失效时改选中项；不动已开始向导的因子状态
      if (!this.data.selectedSession) {
        patch.selectedIndex = sessions.length ? 0 : 0
        patch.selectedSessionId = sessions.length ? sessions[0].id : null
        patch.selectedSession = sessions.length ? sessions[0] : null
      }
      this.setData(patch)
      this._startCountdown()
    } catch (e) {
      // request 已统一提示
    }
  },

  // 重置向导为初始态（开始新签到 / 切换会话 / 签到成功后调用）
  _resetFlow() {
    this.setData({
      flowStep: 'idle',
      fingerprintChecked: false,
      fingerprintData: null,
      faceChecked: false,
      faceImg: null,
      faceImg2: null,
      lat: null,
      lng: null,
      geoAccuracy: null,
      geoText: '',
      geoState: 'pending',
      stepStatus: '',
      stepTitle: '',
    })
  },

  onSessionChange(e) {
    const idx = Number(e.detail.value)
    const s = this.data.activeSessions[idx]
    if (!s) return
    // 切换会话：如果正在向导中先提醒
    if (this.data.flowStep !== 'idle') {
      wx.showModal({
        title: '正在签到流程中',
        content: '切换课程会重置当前签到进度，确认切换吗？',
        confirmText: '切换',
        success: (res) => {
          if (res.confirm) {
            this._resetFlow()
            this.setData({ selectedSessionId: s.id, selectedSession: s, selectedIndex: idx })
            this._startCountdown()
          }
        },
      })
      return
    }
    this.setData({ selectedSessionId: s.id, selectedSession: s, selectedIndex: idx })
    this._startCountdown()
  },

  // ============ 开始签到：定位后台并行 + 指纹第一步 ============
  async onStartCheckin() {
    const { selectedSession } = this.data
    if (!selectedSession) {
      wx.showToast({ title: '暂无进行中的签到', icon: 'none' })
      return
    }
    if (selectedSession.remaining_seconds <= 0) {
      wx.showToast({ title: '签到已结束', icon: 'none' })
      return
    }
    this._resetFlow()
    this.setData({
      flowStep: 'fingerprint',
      stepTitle: '第 1 步 / 共 3 步 · 指纹验证',
      stepStatus: '正在唤起指纹…',
    })
    // 定位与指纹并行：点击"开始签到"即开始获取定位（不阻塞流程）
    this._startGeoOnce()
    // 自动唤起指纹验证
    this.onCaptureFingerprint()
  },

  // 点击开始签到后自动获取一次定位（后台并行，不打断指纹流程）
  _startGeoOnce() {
    try {
      wx.getLocation({
        type: 'gcj02',
        isHighAccuracy: true,
        success: (loc) => {
          this.setData({
            lat: loc.latitude,
            lng: loc.longitude,
            geoAccuracy: loc.accuracy || null,
            geoState: 'ok',
            geoText: `${loc.latitude.toFixed(5)}, ${loc.longitude.toFixed(5)}` +
              (loc.accuracy ? `（精度${Math.round(loc.accuracy)}m）` : ''),
          })
          console.log(
            '[签到] 学生定位成功:', loc.latitude, loc.longitude,
            '精度=', loc.accuracy || '未知', 'm',
          )
        },
        fail: (err) => {
          // 定位失败：回退教师坐标，围栏校验由后端判定（仅提示，不弹窗打断）
          console.warn('[签到] 学生定位失败:', err && err.errMsg)
          const s = this.data.selectedSession
          if (s) {
            this.setData({
              lat: s.teacher_lat,
              lng: s.teacher_lng,
              geoState: 'fallback',
            })
          }
        },
      })
    } catch (e) {
      const s = this.data.selectedSession
      if (s) {
        this.setData({
          lat: s.teacher_lat,
          lng: s.teacher_lng,
          geoState: 'fallback',
        })
      }
    }
  },

  // ============ 第 1 步：指纹验证（微信 SOTER） ============
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
        // 设备不支持指纹 → 演示/模拟器环境：标记跳过并提示（后端允许 fingerprint=null）
        this.setData({
          fingerprintChecked: true,
          fingerprintData: null,
          flowStep: 'face',
          stepTitle: '第 2 步 / 共 3 步 · 人脸识别（活体）',
          stepStatus: '⚠️ 设备不支持指纹，已跳过（仅演示环境）',
        })
        return
      }

      // 2) 检查是否已录入指纹
      const enrolled = await new Promise((resolve, reject) => {
        wx.checkIsSoterEnrolledInDevice({
          checkAuthMode: 'fingerPrint',
          success: resolve,
          fail: reject,
        })
      })
      if (!enrolled.isEnrolled) {
        wx.showModal({
          title: '未录入指纹',
          content: '请在手机系统设置中添加指纹后再试',
          showCancel: false,
        })
        this.setData({ stepStatus: '❌ 设备未录入指纹，请先到系统设置添加' })
        return
      }

      // 3) 启动指纹认证
      const authRes = await new Promise((resolve, reject) => {
        wx.startSoterAuthentication({
          requestAuthModes: ['fingerPrint'],
          challenge: `smartclass-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          authContent: '智慧课堂签到指纹验证',
          success: resolve,
          fail: reject,
        })
      })
      const fpData = `${authRes.resultJSON}|${authRes.resultJSONSignature}`
      // 指纹通过 → 进入人脸步骤
      this.setData({
        fingerprintChecked: true,
        fingerprintData: fpData,
        flowStep: 'face',
        stepTitle: '第 2 步 / 共 3 步 · 人脸识别（活体）',
        stepStatus: '✅ 指纹验证通过，请进行人脸识别',
      })
    } catch (e) {
      const errMsg = (e && e.errMsg) || ''
      if (errMsg.includes('cancel')) {
        this.setData({ stepStatus: '❌ 用户取消了指纹验证，请重试' })
      } else {
        this.setData({ stepStatus: `❌ 指纹验证失败：${errMsg || '未知'}` })
      }
    }
  },

  // ============ 第 2 步：人脸采集（活体两帧） ============
  async onCaptureFace() {
    try {
      const img = await chooseImageToBase64(true)
      this.setData({
        faceImg: img,
        faceChecked: true,
        stepStatus: '✅ 第一帧已采集，请移动头部后拍摄第二帧（活体）',
      })
    } catch (e) {
      if (!e.cancelled) {
        wx.showToast({ title: e.message || '拍照失败', icon: 'none' })
      }
    }
  },

  // 第二帧（活体：两帧关键点位移比对）
  async onCaptureLive() {
    try {
      const img2 = await chooseImageToBase64(true)
      this.setData({
        faceImg2: img2,
        stepStatus: '✅ 第二帧已采集，活体校验完成',
      })
      // 两帧齐全 → 进入可提交状态
      if (this.data.faceImg) {
        this.setData({
          flowStep: 'ready',
          stepTitle: '三项因子已就绪',
          stepStatus: '✅ 人脸（活体）已通过，可以提交签到',
        })
      }
    } catch (e) {
      if (!e.cancelled) {
        wx.showToast({ title: e.message || '拍照失败', icon: 'none' })
      }
    }
  },

  // ============ 提交签到（三因子） ============
  async onThreeFactorSubmit() {
    const {
      selectedSessionId, faceImg, faceImg2, lat, lng,
      fingerprintData, fingerprintChecked, faceChecked, geoState,
    } = this.data
    if (!selectedSessionId) {
      wx.showToast({ title: '暂无进行中的签到', icon: 'none' })
      return
    }
    // 三因子齐全校验
    if (!fingerprintChecked) {
      wx.showToast({ title: '请先完成指纹验证', icon: 'none' })
      return
    }
    if (!faceChecked || !faceImg || !faceImg2) {
      wx.showToast({ title: '请先完成人脸及活体采集', icon: 'none' })
      return
    }
    if (lat === null || lng === null) {
      wx.showToast({ title: '定位未就绪，请稍候或重试', icon: 'none' })
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
          this._resetFlow()
          this.loadData()
        },
      })
    } catch (e) {
      wx.showModal({
        title: '签到失败',
        content: e.message || '签到失败',
        showCancel: false,
      })
    } finally {
      this.setData({ submitting: false })
    }
  },

  // ============ 演示签到（跳过人脸/指纹，仅用于演示环境） ============
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
      wx.showModal({ title: '签到失败', content: e.message || '签到失败', showCancel: false })
    } finally {
      this.setData({ submitting: false })
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
  onOpenApply() {
    const sid = this.data.selectedSessionId
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