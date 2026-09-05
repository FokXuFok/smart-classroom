<template>
  <div class="not-found">
    <div class="not-found-code">404</div>
    <p>页面不存在</p>
    <el-button type="primary" @click="goHome">返回首页</el-button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const auth = useAuthStore();

function goHome() {
  router.replace(auth.isLoggedIn ? `/${auth.role}` : '/login');
}
</script>
