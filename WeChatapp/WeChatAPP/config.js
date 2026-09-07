/**
 * 全局配置
 * API_BASE: 后端服务地址（自动判断模拟器/真机，支持登录页动态切换）
 *
 * 地址优先级（从高到低）：
 *   1) 用户自定义（storage: server_addr，登录页"服务器设置"里保存）
 *   2) 自动探测成功（storage: server_addr 由探测结果写入，规则同 1）
 *   3) 编译期默认（模拟器 127.0.0.1 / 真机 LAN_IP）
 *
 * 真机调试前提：
 *   1) 手机和电脑在同一网络（同一 WiFi/热点，或 USB 网络共享）
 *   2) 后端绑定 0.0.0.0（main.py 已默认）
 *   3) 微信开发者工具 → 详情 → 本地设置 → 勾选"不校验合法域名"
 *
 * 正式发布：HTTPS 域名，并在微信公众平台配置 request 合法域名
 */

// 电脑默认 IP（仅作为兜底：USB 网络共享 / WiFi 下 IP 变化后，
// 请在登录页"服务器设置"里点"自动检测"或手动输入，无需改本文件）
const LAN_IP = '10.90.193.20'
const PORT = 8080

function defaultBase() {
  // 模拟器用 127.0.0.1，真机用 LAN_IP
  try {
    const sys = wx.getSystemInfoSync()
    return sys.platform === 'devtools'
      ? 'http://127.0.0.1:' + PORT
      : 'http://' + LAN_IP + ':' + PORT
  } catch (e) {
    return 'http://127.0.0.1:' + PORT
  }
}

/**
 * 当前生效的 API_BASE：
 * 优先返回用户手动保存/探测成功的地址（storage: server_addr），否则返回编译期默认。
 * 每次调用实时读取，保证在登录页切换服务器后立即生效，无需重启小程序。
 */
function getApiBase() {
  const saved = wx.getStorageSync('server_addr')
  if (saved && typeof saved === 'string' && saved.length > 4) {
    return saved.replace(/\/+$/, '')
  }
  return defaultBase()
}

/**
 * 保存服务器地址（登录页"服务器设置"里调用）
 */
function setApiBase(url) {
  wx.setStorageSync('server_addr', url.replace(/\/+$/, ''))
  console.log('[config] 服务器地址已保存: ' + url)
}

/**
 * 获取探测候选地址列表（自动检测时按序尝试）
 * - 用户已保存的地址
 * - 当前生效地址
 * - 编译期默认地址
 * 去重后返回
 */
function candidateBases() {
  const list = []
  const push = (u) => {
    if (u && list.indexOf(u) === -1) list.push(u)
  }
  push(getApiBase())
  push(defaultBase())
  push('http://' + LAN_IP + ':' + PORT)
  return list
}

const config = {
  get API_BASE() {
    return getApiBase()
  },
  candidateBases,
  setApiBase,
  // 演示签到默认坐标（教师发起签到时使用的坐标，用于演示模式签到回退）
  DEMO_LAT: 25.272,
  DEMO_LNG: 110.331,
  // 签到状态中文映射
  ATT_STATUS_CN: { 0: '缺勤', 1: '正常', 2: '迟到', 3: '早退', 4: '请假' },
  // 提交状态中文映射
  SUBMIT_STATUS_CN: { 0: '待评测', 1: '已评测', 2: '已批改' },
}

module.exports = config