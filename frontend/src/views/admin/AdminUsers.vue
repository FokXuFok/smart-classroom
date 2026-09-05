<template>
  <div class="admin-users">
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <el-radio-group v-model="role" @change="onRoleChange">
          <el-radio-button value="student">学生</el-radio-button>
          <el-radio-button value="teacher">教师</el-radio-button>
          <el-radio-button value="counselor">辅导员</el-radio-button>
          <el-radio-button value="admin">管理员</el-radio-button>
        </el-radio-group>
        <el-input
          v-model="keyword"
          placeholder="按工号/姓名/电话搜索"
          clearable
          class="search-input"
          @keyup.enter="onSearch"
          @clear="onSearch"
        />
        <el-button type="primary" @click="onSearch">搜索</el-button>
        <el-button @click="onReset">重置</el-button>
        <div class="spacer" />
        <el-button
          v-if="role !== 'admin'"
          type="primary"
          @click="openCreate"
        >
          新增{{ roleLabel }}
        </el-button>
      </div>
    </el-card>

    <el-card class="table-card" shadow="never">
      <el-table :data="rows" v-loading="loading" stripe border style="width: 100%">
        <el-table-column prop="user_id" label="工号" width="130" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column label="性别" width="70">
          <template #default="{ row }">{{ genderText(row.gender) }}</template>
        </el-table-column>
        <el-table-column label="电话" width="140">
          <template #default="{ row }">{{ row.phone || '-' }}</template>
        </el-table-column>
        <el-table-column label="邮箱" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column
          v-if="role === 'student'"
          label="班级"
          width="160"
        >
          <template #default="{ row }">
            {{ row.class_name || row.class_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column
          v-if="role === 'teacher' || role === 'counselor'"
          label="院系"
          width="160"
        >
          <template #default="{ row }">{{ row.department || '-' }}</template>
        </el-table-column>
        <el-table-column
          v-if="role === 'teacher'"
          label="职称"
          width="120"
        >
          <template #default="{ row }">{{ row.title || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="onResetPassword(row)">
              重置密码
            </el-button>
            <el-button
              size="small"
              :type="toggleButtonType(row.status)"
              @click="onToggleStatus(row)"
            >
              {{ toggleButtonText(row.status) }}
            </el-button>
            <el-button size="small" type="danger" @click="onDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next, jumper"
          background
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="showEdit"
      :title="editMode === 'create' ? `新增${roleLabel}` : `编辑${roleLabel}`"
      width="520px"
      @closed="onDialogClosed"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="80px"
      >
        <el-form-item v-if="editMode === 'create'" label="工号" prop="user_no">
          <el-input v-model="form.user_no" placeholder="必填" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="form.gender">
            <el-radio :value="1">男</el-radio>
            <el-radio :value="0">女</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="选填" />
        </el-form-item>
        <el-form-item v-if="role === 'student'" label="班级">
          <el-select
            v-model="form.class_id"
            placeholder="选择班级"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="c in classOptions"
              :key="c.class_id"
              :label="`${c.class_id} ${c.class_name}`"
              :value="c.class_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="role === 'teacher' || role === 'counselor'"
          label="院系"
        >
          <el-input v-model="form.department" placeholder="选填" />
        </el-form-item>
        <el-form-item v-if="role === 'teacher'" label="职称">
          <el-input v-model="form.title" placeholder="选填" />
        </el-form-item>
        <el-form-item v-if="editMode === 'edit'" label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="正常" :value="1" />
            <el-option label="禁用" :value="0" />
            <el-option label="待审批" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editMode === 'create'" label="密码">
          <el-input
            v-model="form.password"
            placeholder="留空默认 123456"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { adminApi } from '@/api/admin';
import type { AdminUser, AdminClass } from '@/api/types';

type AdminRole = 'student' | 'teacher' | 'counselor' | 'admin';

const loading = ref(false);
const saving = ref(false);
const role = ref<AdminRole>('student');
const keyword = ref('');
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const rows = ref<AdminUser[]>([]);

const showEdit = ref(false);
const editMode = ref<'create' | 'edit'>('create');
const editingId = ref('');
const classOptions = ref<AdminClass[]>([]);
const formRef = ref<FormInstance>();

const form = reactive({
  user_no: '',
  name: '',
  gender: 1,
  phone: '',
  email: '',
  class_id: '',
  department: '',
  title: '',
  status: 1,
  password: '',
});

const formRules: FormRules = {
  user_no: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
};

const roleLabel = computed(
  () =>
    ({
      student: '学生',
      teacher: '教师',
      counselor: '辅导员',
      admin: '管理员',
    })[role.value],
);

function genderText(g?: number) {
  if (g === 1) return '男';
  if (g === 0) return '女';
  return '-';
}

function statusText(s?: number) {
  if (s === 0) return '禁用';
  if (s === 1) return '正常';
  if (s === 2) return '待审批';
  return '-';
}

function statusTagType(s?: number): 'danger' | 'success' | 'warning' | 'info' {
  if (s === 0) return 'danger';
  if (s === 1) return 'success';
  if (s === 2) return 'warning';
  return 'info';
}

function toggleButtonText(s?: number) {
  if (s === 2) return '审批通过';
  if (s === 1) return '禁用';
  if (s === 0) return '启用';
  return '切换';
}

function toggleButtonType(s?: number): 'success' | 'danger' | 'primary' {
  if (s === 2) return 'success';
  if (s === 1) return 'danger';
  return 'primary';
}

function fmtTime(t?: string): string {
  if (!t) return '-';
  const d = new Date(t);
  if (isNaN(d.valueOf())) return t;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(
    d.getDate(),
  )} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function load() {
  loading.value = true;
  try {
    const res = await adminApi.listUsers({
      role: role.value,
      keyword: keyword.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    });
    rows.value = res.items;
    total.value = res.total;
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

async function loadClasses() {
  try {
    classOptions.value = await adminApi.listClasses();
  } catch {
    /* 静默 */
  }
}

function onRoleChange() {
  page.value = 1;
  keyword.value = '';
  load();
}

function onSearch() {
  page.value = 1;
  load();
}

function onReset() {
  keyword.value = '';
  page.value = 1;
  load();
}

function resetForm() {
  form.user_no = '';
  form.name = '';
  form.gender = 1;
  form.phone = '';
  form.email = '';
  form.class_id = '';
  form.department = '';
  form.title = '';
  form.status = 1;
  form.password = '';
}

function openCreate() {
  editMode.value = 'create';
  editingId.value = '';
  resetForm();
  if (role.value === 'student') loadClasses();
  showEdit.value = true;
}

function openEdit(row: AdminUser) {
  editMode.value = 'edit';
  editingId.value = row.user_id;
  form.user_no = row.user_id;
  form.name = row.name;
  form.gender = row.gender ?? 1;
  form.phone = row.phone ?? '';
  form.email = row.email ?? '';
  form.class_id = row.class_id ?? '';
  form.department = row.department ?? '';
  form.title = row.title ?? '';
  form.status = row.status ?? 1;
  form.password = '';
  if (role.value === 'student') loadClasses();
  showEdit.value = true;
}

function onDialogClosed() {
  formRef.value?.clearValidate();
  resetForm();
}

async function onSubmit() {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;
  saving.value = true;
  try {
    if (editMode.value === 'create') {
      const payload: Parameters<typeof adminApi.createUser>[0] = {
        role: role.value as 'student' | 'teacher' | 'counselor',
        user_no: form.user_no,
        name: form.name,
        gender: form.gender,
        phone: form.phone || undefined,
        email: form.email || undefined,
      };
      if (role.value === 'student') payload.class_id = form.class_id || undefined;
      if (role.value === 'teacher' || role.value === 'counselor')
        payload.department = form.department || undefined;
      if (role.value === 'teacher') payload.title = form.title || undefined;
      if (form.password) payload.password = form.password;
      await adminApi.createUser(payload);
      ElMessage.success('创建成功');
    } else {
      const payload: Parameters<typeof adminApi.updateUser>[2] = {
        name: form.name,
        gender: form.gender,
        phone: form.phone || undefined,
        email: form.email || undefined,
        status: form.status,
      };
      if (role.value === 'student') payload.class_id = form.class_id || undefined;
      if (role.value === 'teacher' || role.value === 'counselor')
        payload.department = form.department || undefined;
      if (role.value === 'teacher') payload.title = form.title || undefined;
      await adminApi.updateUser(role.value, editingId.value, payload);
      ElMessage.success('保存成功');
    }
    showEdit.value = false;
    load();
  } catch {
    /* http.ts 已 toast */
  } finally {
    saving.value = false;
  }
}

async function onResetPassword(row: AdminUser) {
  try {
    await ElMessageBox.confirm(
      `确认重置「${row.name}」的密码?`,
      '重置密码',
      { type: 'warning' },
    );
    await adminApi.resetPassword(role.value, row.user_id);
    ElMessage.success('密码已重置为 123456');
  } catch (e) {
    if (e !== 'cancel') {
      /* http.ts 已 toast */
    }
  }
}

async function onToggleStatus(row: AdminUser) {
  try {
    await adminApi.toggleStatus(role.value, row.user_id);
    load();
  } catch {
    /* http.ts 已 toast */
  }
}

async function onDelete(row: AdminUser) {
  try {
    await ElMessageBox.confirm(
      `确认删除「${row.name}」? 若该用户存在业务数据(选课/签到等),后端将拒绝删除.`,
      '删除用户',
      { type: 'warning' },
    );
    await adminApi.deleteUser(role.value, row.user_id);
    ElMessage.success('已删除');
    load();
  } catch (e) {
    if (e !== 'cancel') {
      /* http.ts 已 toast */
    }
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
.admin-users {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.search-input {
  width: 260px;
}
.spacer {
  flex: 1;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
