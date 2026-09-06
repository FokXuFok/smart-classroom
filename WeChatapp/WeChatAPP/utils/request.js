// utils/request.js
const config = require('../config')
const app = getApp()

/**
 * 统一请求封装
 *
 * Cookie 策略：
 * 小程序的 wx.request 对 HttpOnly + SameSite=Lax 的 cookie 自动管理不稳定，
 * 因此改为手动管理：从响应头 Set-Cookie 提取 sc_token_* 存 storage，每次请求带上。
 *
 * 后端响应格式：
 *   成功：{ code: 0, message: "ok", data: ... }
 *   失败：{ code: 非0, message: "错误信息" }（HTTP 始终 200）
 *
 * @param {string} path - 接口路径（如 /api/student/courses）
 * @param {object} options - { method, data, role, silent }
 *   role: 声明当前角色，注入 X-Role 头（/me、通知等不限定角色的接口需要）
 *   silent: true 时 401 不自动跳登录
 */
function getCookies() {
  return wx.getStorageSync('cookies') || {}
}

function setCookie(name, value) {
  const cookies = getCookies()
  // 去掉 value 可能带的属性（; Path=/; HttpOnly 等）
  cookies[name] = value.split(';')[0]
  wx.setStorageSync('cookies', cookies)
}

function buildCookieHeader(role) {
  const cookies = getCookies()
  const key = `sc_token_${role}`
  if (cookies[key]) {
    return `${key}=${cookies[key]}`
  }
  return ''
}

function request(path, options) {
  options = options || {}
  const method = (options.method || 'GET').toUpperCase()
  const role = options.role || 'student'

  const header = {
    'Content-Type': 'application/json',
    'X-Role': role,
  }
  // 手动带上当前角色 cookie
  const cookieStr = buildCookieHeader(role)
  if (cookieStr) {
    header['Cookie'] = cookieStr
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: config.API_BASE + path,
      method: method,
      data: options.data,
      header: header,
      timeout: 20000,
      success: (res) => {
        // 从响应头提取 Set-Cookie，手动存储
        const setCookieHeader =
          res.header['Set-Cookie'] || res.header['set-cookie']
        if (setCookieHeader) {
          // Set-Cookie 可能是字符串或数组
          const list = Array.isArray(setCookieHeader)
            ? setCookieHeader
            : [setCookieHeader]
          list.forEach((line) => {
            // 格式：sc_token_student=xxx; Path=/; HttpOnly; SameSite=Lax
            const m = line.match(/^([^=]+)=([^;]*)/)
            if (m) setCookie(m[1], m[2])
          })
        }

        const body = res.data
        if (!body || typeof body !== 'object') {
          reject({ code: -2, message: '响应格式错误' })
          return
        }
        if (body.code === 0) {
          resolve(body.data)
          return
        }
        // 401 未登录/登录失效
        if (body.code === 401) {
          if (!options.silent) {
            if (app && app.clearUserInfo) app.clearUserInfo()
            wx.showToast({ title: '登录已过期，请重新登录', icon: 'none' })
            setTimeout(() => {
              wx.reLaunch({ url: '/pages/login/login' })
            }, 800)
          }
          reject({ code: 401, message: body.message || '未登录或登录已过期' })
          return
        }
        // 其他业务错误
        reject({ code: body.code, message: body.message || '请求失败' })
      },
      fail: (err) => {
        reject({
          code: -1,
          message: '无法连接服务器，请确认后端已启动（' + config.API_BASE + '）',
        })
      },
    })
  })
}

module.exports = {
  get: (path, options) => request(path, Object.assign({ method: 'GET' }, options || {})),
  post: (path, data, options) =>
    request(path, Object.assign({ method: 'POST', data: data }, options || {})),
  request,
}
