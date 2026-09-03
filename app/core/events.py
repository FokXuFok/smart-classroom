# -*- coding: utf-8 -*-
"""进程内 SSE 事件总线：签到会话实时事件推送

设计要点：
- 订阅者持有 (event_loop, asyncio.Queue) 二元组；发布方通过
  loop.call_soon_threadsafe 投递事件，保证同步线程池端点（签到提交等
  sync def 路由）能安全地向异步 SSE 端点发布，不触碰 asyncio 非线程安全 API；
- 单进程内存版（与 JWT 黑名单同一演示口径），生产需换 Redis Pub/Sub。
"""
import asyncio
import threading


class SessionBus:
    """按签到会话 id 分组的发布/订阅总线"""

    def __init__(self):
        self._subs = {}  # session_id -> set[(loop, queue)]
        self._lock = threading.Lock()

    def subscribe(self, session_id: int) -> asyncio.Queue:
        """订阅指定会话（须在事件循环内调用）；返回事件队列"""
        q = asyncio.Queue(maxsize=100)
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subs.setdefault(session_id, set()).add((loop, q))
        return q

    def unsubscribe(self, session_id: int, q: asyncio.Queue) -> None:
        """退订（SSE 连接断开时由 finally 调用）"""
        with self._lock:
            subs = self._subs.get(session_id)
            if not subs:
                return
            for pair in [p for p in subs if p[1] is q]:
                subs.discard(pair)
            if not subs:
                self._subs.pop(session_id, None)

    def publish(self, session_id: int, event: dict) -> None:
        """向该会话的全部订阅者发布事件（线程安全，无订阅者时为空操作）"""
        with self._lock:
            pairs = list(self._subs.get(session_id, ()))
        for loop, q in pairs:
            try:
                loop.call_soon_threadsafe(self._offer, q, event)
            except RuntimeError:
                pass  # 订阅者事件循环已关闭（页面已关），忽略

    @staticmethod
    def _offer(q: asyncio.Queue, event: dict) -> None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # 慢消费者丢帧：前端重新打开看板时会收到快照补齐


# 全局单例：签到会话实时事件（checkin / review / session_end / review_done）
checkin_bus = SessionBus()
