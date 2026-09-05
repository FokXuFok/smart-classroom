<template>
  <div class="admin-classes" v-loading="loading">
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增班级</el-button>
    </div>

    <el-card>
      <el-table :data="classes" border stripe>
        <el-table-column prop="class_id" label="班级号" width="160" />
        <el-table-column prop="class_name" label="班级名称" min-width="220" />
        <el-table-column label="年级" width="100">
          <template #default="{ row }">{{ row.grade || '-' }}</template>
        </el-table-column>
        <el-table-column label="专业" min-width="180">
          <template #default="{ row }">{{ row.major || '-' }}</template>
        </el-table-column>
        <el-table-column label="院系" min-width="180">
          <template #default="{ row }">{{ row.department || '-' }}</template>
        </el-table-column>
        <el-table-column
          prop="student_count"
          label="学生数"
          width="90"
          align="center"
        />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="openEdit(row)">
              编辑
            </el-button>
            <el-tooltip content="暂不支持删除" placement="top">
              <span class="disabled-wrap">
                <el-button type="danger" size="small" link disabled>
                  删除
                </el-button>
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增班级' : '编辑班级'"
      width="520px"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="班级号" prop="class_id">
          <el-input
            v-model="form.class_id"
            :disabled="dialogMode === 'edit'"
            placeholder="如 CS2024-1"
          />
        </el-form-item>
        <el-form-item label="班级名称" prop="class_name">
          <el-input
            v-model="form.class_name"
            placeholder="如 计算机科学与技术2024-1班"
          />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-input v-model="form.grade" placeholder="如 2024（可选）" />
        </el-form-item>
        <el-form-item label="专业" prop="major">
          <el-input
            v-model="form.major"
            placeholder="如 计算机科学与技术（可选）"
          />
        </el-form-item>
        <el-form-item label="院系" prop="department">
          <el-input v-model="form.department" placeholder="如 计算机学院（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          @click="handleSubmit"
        >提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, type FormInstance, type FormRules } from 'element-plus';
import { adminApi } from '@/api/admin';
import type { AdminClass } from '@/api/types';

const loading = ref(false);
const submitting = ref(false);
const classes = ref<AdminClass[]>([]);

const dialogVisible = ref(false);
const dialogMode = ref<'create' | 'edit'>('create');
const formRef = ref<FormInstance>();
const form = reactive({
  class_id: '',
  class_name: '',
  grade: '',
  major: '',
  department: '',
});
const rules: FormRules = {
  class_id: [{ required: true, message: '请输入班级号', trigger: 'blur' }],
  class_name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }],
};

async function load() {
  loading.value = true;
  try {
    classes.value = await adminApi.listClasses();
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  formRef.value?.clearValidate();
  form.class_id = '';
  form.class_name = '';
  form.grade = '';
  form.major = '';
  form.department = '';
}

function openCreate() {
  dialogMode.value = 'create';
  resetForm();
  dialogVisible.value = true;
}

function openEdit(row: AdminClass) {
  dialogMode.value = 'edit';
  form.class_id = row.class_id;
  form.class_name = row.class_name;
  form.grade = row.grade ?? '';
  form.major = row.major ?? '';
  form.department = row.department ?? '';
  dialogVisible.value = true;
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;
  submitting.value = true;
  try {
    if (dialogMode.value === 'create') {
      await adminApi.createClass({
        class_id: form.class_id,
        class_name: form.class_name,
        grade: form.grade || undefined,
        major: form.major || undefined,
        department: form.department || undefined,
      });
      ElMessage.success('班级已创建');
    } else {
      await adminApi.updateClass(form.class_id, {
        class_name: form.class_name,
        grade: form.grade || undefined,
        major: form.major || undefined,
        department: form.department || undefined,
      });
      ElMessage.success('班级已更新');
    }
    dialogVisible.value = false;
    await load();
  } catch {
    /* http.ts 已 toast */
  } finally {
    submitting.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
.admin-classes {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.toolbar {
  display: flex;
  justify-content: flex-end;
}
.card-title {
  font-weight: 600;
}
.disabled-wrap {
  display: inline-flex;
  margin-left: 4px;
}
</style>
