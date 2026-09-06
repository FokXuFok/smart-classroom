// utils/image.js
/**
 * 图片工具：拍照/选图 → base64
 * 用于人脸注册和签到时的照片上传
 */

/**
 * 拍摄或选择照片，返回 base64 字符串（带 data URI 前缀，后端可自动处理）
 * @param {boolean} useCamera - true 仅拍照，false 仅从相册选，undefined 两者皆可
 * @returns {Promise<string>} base64 图片（data:image/jpeg;base64,xxx）
 */
function chooseImageToBase64(useCamera) {
  return new Promise((resolve, reject) => {
    const sourceType =
      useCamera === true ? ['camera'] : useCamera === false ? ['album'] : ['camera', 'album']

    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: sourceType,
      camera: 'front',
      sizeType: ['compressed'],
      success: (res) => {
        const tempFile = res.tempFiles[0]
        const fs = wx.getFileSystemManager()
        fs.readFile({
          filePath: tempFile.tempFilePath,
          encoding: 'base64',
          success: (r) => {
            const base64 = 'data:image/jpeg;base64,' + r.data
            resolve(base64)
          },
          fail: (err) => reject({ message: '图片读取失败', err }),
        })
      },
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('cancel') > -1) {
          reject({ message: '已取消', cancelled: true })
        } else {
          reject({ message: '获取图片失败', err })
        }
      },
    })
  })
}

module.exports = { chooseImageToBase64 }
