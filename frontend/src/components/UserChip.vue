<template>
  <el-dropdown trigger="click" @command="onCommand">
    <span class="user-chip">
      <el-avatar :size="32" class="user-avatar">{{ (auth.name || '?').charAt(0) }}</el-avatar>
      <span class="user-name">{{ auth.name }}</span>
      <el-tag size="small" :type="roleTagType">{{ auth.roleCn }}</el-tag>
      <el-icon><ArrowDown /></el-icon>
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="logout">
          <el-icon><SwitchButton /></el-icon>
          <span>退出登录</span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessageBox } from 'element-plus';
import { useAuthStore } from '@/stores/auth';
import { ROLE_TAG_TYPE } from '@/utils/constants';

const auth = useAuthStore();
const router = useRouter();

const roleTagType = computed(
  () => ROLE_TAG_TYPE[auth.role] || 'info',
);

async function onCommand(cmd: string) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确定退出登录?', '提示', {
        type: 'warning',
      });
    } catch {
      return;
    }
    await auth.logout();
    router.replace('/login');
  }
}
</script>
