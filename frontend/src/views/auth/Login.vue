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
        <el-tab-pane label="注册" name="register">
          <el-form
            :model="regForm"
            label-position="top"
            @submit.prevent="onRegister"
          >
            <el-form-item label="身份">
              <el-radio-group v-model="regForm.role">
                <el-radio value="student">学生</el-radio>
                <el-radio value="teacher">教师</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item :label="regForm.role === 'student' ? '学号' : '工号'">
              <el-input
                v-model="regForm.username"
                :placeholder="regForm.role === 'student' ? '请输入学号' : '请输入工号'"
                :prefix-icon="User"
                clearable
              />
            </el-form-item>
            <el-form-item label="姓名">
              <el-input v-model="regForm.name" placeholder="真实姓名" clearable />
            </el-form-item>
            <el-form-item v-if="regForm.role === 'student'" label="班级" required>
              <el-select
                v-model="regForm.class_id"
                placeholder="选择班级"
                style="width: 100%"
                :loading="classLoading"
              >
                <el-option
                  v-for="c in classOptions"
                  :key="c.class_code"
                  :label="`${c.class_name}（${c.class_code}）`"
                  :value="c.class_code"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="密码（至少 6 位）">
              <el-input
                v-model="regForm.password"
                type="password"
                placeholder="设置密码"
                show-password
                :prefix-icon="Lock"
              />
            </el-form-item>
            <el-button
              type="primary"
              :loading="regLoading"
              class="login-btn"
              @click="onRegister"
            >
              提交注册
            </el-button>
          </el-form>
          <div class="reg-tip">
            注册账号需等待管理员审批，审核通过后方可登录。
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { User, Lock } from '@element-plus/icons-vue';
import { useAuthStore } from '@/stores/auth';
import { authApi } from '@/api/auth';
import { DEMO_ACCOUNTS } from '@/utils/constants';
import type { ClassOption } from '@/api/types';

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const activeTab = ref('login');
const loading = ref(false);
const loginForm = reactive({ username: '', password: '' });

// 注册表单
const classLoading = ref(false);
const classOptions = ref<ClassOption[]>([]);
const regLoading = ref(false);
const regForm = reactive<{
  role: 'student' | 'teacher';
  username: string;
  name: string;
  password: string;
  class_id: string;
}>({
  role: 'student',
  username: '',
  name: '',
  password: '',
  class_id: '',
});

async function loadClassOptions() {
  classLoading.value = true;
  try {
    classOptions.value = await authApi.classOptions();
  } catch {
    classOptions.value = [];
  } finally {
    classLoading.value = false;
  }
}

async function onRegister() {
  const username = regForm.username.trim();
  const name = regForm.name.trim();
  if (!username) {
    ElMessage.warning(regForm.role === 'student' ? '请输入学号' : '请输入工号');
    return;
  }
  if (!name) {
    ElMessage.warning('请输入姓名');
    return;
  }
  if (!regForm.password || regForm.password.length < 6) {
    ElMessage.warning('密码至少 6 位');
    return;
  }
  if (regForm.role === 'student' && !regForm.class_id) {
    ElMessage.warning('学生请选择班级');
    return;
  }
  regLoading.value = true;
  try {
    await authApi.register({
      username,
      name,
      password: regForm.password,
      role: regForm.role,
      class_id: regForm.role === 'student' ? regForm.class_id : undefined,
    });
    ElMessage.success('注册成功，请等待管理员审核通过后登录');
    loginForm.username = username;
    loginForm.password = '';
    regForm.password = '';
    regForm.username = '';
    regForm.name = '';
    regForm.class_id = '';
    activeTab.value = 'login';
  } catch {
    /* http.ts 已 toast */
  } finally {
    regLoading.value = false;
  }
}

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

onMounted(loadClassOptions);
</script>

<style scoped lang="scss">
.reg-tip {
  margin-top: 12px;
  font-size: 12px;
  color: var(--text-sub);
  text-align: center;
  line-height: 1.6;
}
</style>
