// SSE 实时签到流封装:用 @microsoft/fetch-event-source(原生 EventSource 不支持自定义头)
// 后端端点:GET /api/teacher/checkin/{id}/stream
// 事件:snapshot(首帧 event 名)/ checkin / review / review_done / session_end(type 在 data JSON)
import { onMounted, onUnmounted } from 'vue';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import type {
  SseEvent,
  SseSnapshot,
  SseCheckin,
  SseReview,
  SseReviewDone,
  SseSessionEnd,
} from '@/api/types';

export interface CheckinStreamCallbacks {
  onSnapshot?: (e: SseSnapshot) => void;
  onCheckin?: (e: SseCheckin) => void;
  onReview?: (e: SseReview) => void;
  onReviewDone?: (e: SseReviewDone) => void;
  onSessionEnd?: (e: SseSessionEnd) => void;
  onError?: (err: Event) => void;
}

export function useCheckinStream(
  sessionId: number,
  callbacks: CheckinStreamCallbacks,
) {
  const ctrl = new AbortController();
  let retryCount = 0;
  const url = `${import.meta.env.VITE_API_BASE}/teacher/checkin/${sessionId}/stream`;

  const start = () =>
    fetchEventSource(url, {
      method: 'GET',
      headers: { 'X-Role': 'teacher', Accept: 'text/event-stream' },
      credentials: 'include',
      signal: ctrl.signal,
      onopen: async (res) => {
        if (res.ok) {
          retryCount = 0;
          return;
        }
        throw new Error(`SSE 连接失败: ${res.status}`);
      },
      onmessage(ev) {
        // 首帧 event:snapshot(ev.event 有值);后续 event 为空,type 在 data JSON
        if (ev.event === 'snapshot') {
          const data = safeParse(ev.data);
          if (data) callbacks.onSnapshot?.(data);
          return;
        }
        const data = safeParse(ev.data);
        if (!data?.type) return;
        const e = data as SseEvent;
        switch (e.type) {
          case 'checkin':
            callbacks.onCheckin?.(e);
            break;
          case 'review':
            callbacks.onReview?.(e);
            break;
          case 'review_done':
            callbacks.onReviewDone?.(e);
            break;
          case 'session_end':
            callbacks.onSessionEnd?.(e);
            ctrl.abort();
            break;
        }
      },
      onerror(err) {
        callbacks.onError?.(err);
        if (ctrl.signal.aborted) return; // 主动 abort(session_end)不重连
        retryCount++;
        if (retryCount > 5) throw err; // 超限终止
        return new Promise((r) => setTimeout(r, 1000 * 2 ** retryCount));
      },
    });

  onMounted(() => start().catch(() => {}));
  onUnmounted(() => ctrl.abort());

  return { stop: () => ctrl.abort() };
}

function safeParse(s: string | undefined): any {
  if (!s) return null;
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}
