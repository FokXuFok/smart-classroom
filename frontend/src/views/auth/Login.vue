<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <span class="brand-logo">智</span>
        <h1>智课堂</h1>
        <p>教 · 学 · 评 · 管 一体化</p>
      </div>
      <el-tabs v-model="activeTab" class="login-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" label-position="top" @submit.prevent="onLogin">
            <el-form-item label="账号">
              <el-input
                v-model="loginForm.username"
                placeholder="账号"
                :prefix-icon="User"
                clearable
              />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="密码"
                show-password
                :prefix-icon="Lock"
                @keyup.enter="onLogin"
              />
            </el-form-item>
            <el-button
              type="primary"
              :loading="loading"
              class="login-btn"
              @click="onLogin"
            >
              登录
            </el-button>
          </el-form>
          <div class="demo-accounts">
            <div class="demo-title">演示账号(点击填充)</div>
            <div class="demo-list">
              <el-button
                v-for="d in demoAccounts"
                :key="d.label"
                size="small"
                @click="fillDemo(d)"
              >
                {{ d.label }}
              </el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { User, Lock } from '@element-plus/icons-vue';
import { useAuthStore } from '@/stores/auth';
import { DEMO_ACCOUNTS } from '@/utils/constants';

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const activeTab = ref('login');
const loading = ref(false);
const loginForm = reactive({ username: '', password: '' });

const demoAccounts = DEMO_ACCOUNTS;

function fillDemo(d: { username: string; password: string }) {
  loginForm.username = d.username;
  loginForm.password = d.password;
}

async function onLogin() {
  if (!loginForm.username || !loginForm.password) {
    ElMessage.warning('请输入账号和密码');
    return;
  }
  loading.value = true;
  try {
    await auth.login({
      username: loginForm.username,
      password: loginForm.password,
    });
    ElMessage.success('登录成功');
    const redirect = (route.query.redirect as string) || `/${auth.role}`;
    router.replace(redirect);
  } catch {
    // http.ts 响应拦截器已统一 toast,这里不重复
  } finally {
    loading.value = false;
  }
}
</script>
