import dayjs from 'dayjs';

// 时间格式化(迁移自 web/js/common.js fmtTime)
export function fmtTime(t: string | number | Date | null | undefined, fmt = 'YYYY-MM-DD HH:mm'): string {
  if (!t) return '';
  const d = dayjs(t);
  return d.isValid() ? d.format(fmt) : String(t);
}

export function fmtDate(t: string | number | Date | null | undefined): string {
  return fmtTime(t, 'YYYY-MM-DD');
}

// 相对时间(几分钟前)
export function fmtFromNow(t: string | number | Date | null | undefined): string {
  if (!t) return '';
  const d = dayjs(t);
  if (!d.isValid()) return String(t);
  const diff = Date.now() - d.valueOf();
  const min = Math.floor(diff / 60000);
  if (min < 1) return '刚刚';
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} 天前`;
  return d.format('YYYY-MM-DD');
}
