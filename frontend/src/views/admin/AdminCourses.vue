<template>
  <div class="admin-courses" v-loading="loading">
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新增课程</el-button>
    </div>

    <el-card>
      <el-table :data="courses" border stripe>
        <el-table-column prop="course_id" label="课程号" width="140" />
        <el-table-column prop="course_name" label="课程名称" min-width="200" />
        <el-table-column label="学分" width="80" align="center">
          <template #default="{ row }">{{ row.credit ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="学时" width="80" align="center">
          <template #default="{ row }">{{ row.hours ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="学期" width="140">
          <template #default="{ row }">{{ row.semester || '-' }}</template>
        </el-table-column>
        <el-table-column label="授课教师" width="140">
          <template #default="{ row }">
            {{ row.teacher_name || row.teacher_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column
          prop="student_count"
          label="学生数"
          width="90"
          align="center"
        />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="openEdit(row)">
              编辑
            </el-button>
            <el-popconfirm
              title="确定删除该课程吗？关联数据将阻止删除。"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" size="small" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增课程' : '编辑课程'"
      width="560px"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="课程号" prop="course_id">
          <el-input
            v-model="form.course_id"
            :disabled="dialogMode === 'edit'"
            placeholder="如 CS101"
          />
        </el-form-item>
        <el-form-item label="课程名称" prop="course_name">
          <el-input v-model="form.course_name" placeholder="如 数据结构" />
        </el-form-item>
        <el-form-item label="学分" prop="credit">
          <el-input-number
            v-model="form.credit"
            :min="0"
            :max="20"
            :step="0.5"
            :precision="1"
            controls-position="right"
            style="width: 100%"
            placeholder="可选"
          />
        </el-form-item>
        <el-form-item label="学时" prop="hours">
          <el-input-number
            v-model="form.hours"
            :min="0"
            :max="500"
            :step="1"
            controls-position="right"
            style="width: 100%"
            placeholder="可选"
          />
        </el-form-item>
        <el-form-item label="学期" prop="semester">
          <el-input v-model="form.semester" placeholder="如 2025-2026-1（可选）" />
        </el-form-item>
        <el-form-item label="授课教师" prop="teacher_id">
          <el-select
            v-model="form.teacher_id"
            filterable
            placeholder="请选择教师"
            style="width: 100%"
          >
            <el-option
              v-for="t in teachers"
              :key="t.user_id"
              :label="`${t.name} (${t.user_id})`"
              :value="t.user_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
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
import type { AdminCourse, AdminUser } from '@/api/types';

const loading = ref(false);
const submitting = ref(false);
const courses = ref<AdminCourse[]>([]);
const teachers = ref<AdminUser[]>([]);

const dialogVisible = ref(false);
const dialogMode = ref<'create' | 'edit'>('create');
const formRef = ref<FormInstance>();
const form = reactive({
  course_id: '',
  course_name: '',
  credit: undefined as number | undefined,
  hours: undefined as number | undefined,
  semester: '',
  teacher_id: '',
  status: 1,
});
const rules: FormRules = {
  course_id: [{ required: true, message: '请输入课程号', trigger: 'blur' }],
  course_name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  teacher_id: [
    { required: true, message: '请选择授课教师', trigger: 'change' },
  ],
};

async function loadTeachers() {
  try {
    const res = await adminApi.listUsers({ role: 'teacher', page_size: 100 });
    teachers.value = res.items;
  } catch {
    /* http.ts 已 toast */
  }
}

async function load() {
  loading.value = true;
  try {
    courses.value = await adminApi.listCourses();
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  formRef.value?.clearValidate();
  form.course_id = '';
  form.course_name = '';
  form.credit = undefined;
  form.hours = undefined;
  form.semester = '';
  form.teacher_id = '';
  form.status = 1;
}

function openCreate() {
  dialogMode.value = 'create';
  resetForm();
  dialogVisible.value = true;
}

function openEdit(row: AdminCourse) {
  dialogMode.value = 'edit';
  form.course_id = row.course_id;
  form.course_name = row.course_name;
  form.credit = row.credit ?? undefined;
  form.hours = row.hours ?? undefined;
  form.semester = row.semester ?? '';
  form.teacher_id = row.teacher_id ?? '';
  form.status = row.status;
  dialogVisible.value = true;
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;
  submitting.value = true;
  try {
    if (dialogMode.value === 'create') {
      await adminApi.createCourse({
        course_id: form.course_id,
        course_name: form.course_name,
        teacher_id: form.teacher_id,
        status: form.status,
        credit: form.credit,
        hours: form.hours,
        semester: form.semester || undefined,
      });
      ElMessage.success('课程已创建');
    } else {
      await adminApi.updateCourse(form.course_id, {
        course_name: form.course_name,
        teacher_id: form.teacher_id,
        status: form.status,
        credit: form.credit,
        hours: form.hours,
        semester: form.semester || undefined,
      });
      ElMessage.success('课程已更新');
    }
    dialogVisible.value = false;
    await load();
  } catch {
    /* http.ts 已 toast */
  } finally {
    submitting.value = false;
  }
}

async function handleDelete(row: AdminCourse) {
  try {
    await adminApi.deleteCourse(row.course_id);
    ElMessage.success('已删除');
    await load();
  } catch {
    /* http.ts 已 toast */
  }
}

onMounted(async () => {
  await Promise.all([load(), loadTeachers()]);
});
</script>

<style scoped lang="scss">
.admin-courses {
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
</style>
