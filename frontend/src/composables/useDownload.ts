// 文件下载:用 a 标签触发,浏览器自动带 cookie(走 Vite 代理同源)
// 不能用 axios blob(会丢 Set-Cookie 处理)
export function useDownload() {
  function download(url: string, filename?: string) {
    const a = document.createElement('a');
    a.href = url;
    if (filename) a.download = filename;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
  return { download };
}
