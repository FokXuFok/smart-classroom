<template>
  <el-container class="layout">
    <el-aside width="236px" class="sidebar">
      <div class="brand">
        <span class="brand-logo">智</span>
        <span class="brand-title">智课堂</span>
      </div>
      <el-menu :default-active="route.path" class="menu" @select="onMenuSelect">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon || 'Menu'" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <PageHeader :title="currentTitle" />
        <div class="topbar-right">
          <NotificationBell />
          <UserChip />
        </div>
      </el-header>
      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useNotificationStore } from '@/stores/notification';
import { getMenus } from '@/router/menus';
import PageHeader from '@/components/PageHeader.vue';
import UserChip from '@/components/UserChip.vue';
import NotificationBell from '@/components/NotificationBell.vue';

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const notif = useNotificationStore();

const menus = computed(() => getMenus(auth.role));
const currentTitle = computed(() => (route.meta.title as string) || '');

function onMenuSelect(path: string) {
  router.push(path);
}

onMounted(() => notif.startPolling());
onUnmounted(() => notif.stopPolling());
</script>
