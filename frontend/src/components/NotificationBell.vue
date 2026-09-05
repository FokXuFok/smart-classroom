<template>
  <el-popover trigger="click" placement="bottom-end" :width="380" @show="onShow">
    <template #reference>
      <el-badge
        :value="notif.unreadCount"
        :hidden="notif.unreadCount === 0"
        :max="99"
        class="bell-badge"
      >
        <el-icon :size="20"><Bell /></el-icon>
      </el-badge>
    </template>
    <div class="notif-panel">
      <div class="notif-header">
        <span>通知</span>
        <el-button
          text
          type="primary"
          size="small"
          :disabled="notif.unreadCount === 0"
          @click="notif.markAllRead()"
        >
          全部已读
        </el-button>
      </div>
      <div class="notif-list">
        <div v-if="notif.items.length === 0" class="notif-empty">暂无通知</div>
        <div
          v-for="n in notif.items"
          :key="n.id"
          class="notif-item"
          :class="{ unread: !n.is_read }"
          @click="onRead(n)"
        >
          <div class="notif-title">{{ n.title || '通知' }}</div>
          <div class="notif-content">{{ n.content }}</div>
          <div class="notif-time">{{ fmtFromNow(n.create_time) }}</div>
        </div>
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { useNotificationStore } from '@/stores/notification';
import { fmtFromNow } from '@/utils/format';
import type { NotificationItem } from '@/api/types';

const notif = useNotificationStore();

function onShow() {
  notif.refresh();
}

function onRead(n: NotificationItem) {
  if (!n.is_read) notif.markRead(n.id);
}
</script>
