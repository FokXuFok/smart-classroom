<template>
  <div class="admin-enrollments" v-loading="loading">
    <el-card>
      <template #header>
        <div class="header-bar">
          <span class="card-title">选课管理</span>
          <div class="header-actions">
            <el-select
              v-model="filterCourseId"
              placeholder="全部课程"
              clearable
              style="width: 220px"
              @change="load"
            >
              <el-option label="全部课程" value="" />
              <el-option
                v-for="c in courses"
                :key="c.course_id"
                :label="`${c.course_id} - ${c.course_name}`"
                :value="c.course_id"
              />
            </el-select>
            <el-button @click="load">刷新</el-button>
            <el-button type="primary" @click="openCreate">新增选课</el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="课程" min-width="160">
          <template #default="{ row }">
            {{ row.course_name || row.course_id }}
          </template>
        </el-table-column>
        <el-table-column prop="student_no" label="学号" width="140" />
        <el-table-column label="姓名" width="120">
          <template #default="{ row }">
            {{ row.student_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '选中' : '退选' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" min-width="160" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确定退选该记录吗？"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" size="small" link>退选</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新增选课" width="460px">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="80px"
      >
        <el-form-item label="课程" prop="course_id">
          <el-select
            v-model="form.course_id"
            placeholder="请选择课程"
            style="width: 100%"
          >
            <el-option
              v-for="c in courses"
              :key="c.course_id"
              :label="`${c.course_id} - ${c.course_name}`"
              :value="c.course_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="学号" prop="student_no">
          <el-input v-model="form.student_no" placeholder="请输入学号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          @click="handleCreate"
        >提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, type FormInstance, type FormRules } from 'element-plus';
import { adminApi } from '@/api/admin';
import type { AdminEnrollment, AdminCourse } from '@/api/types';

const loading = ref(false);
const submitting = ref(false);
const list = ref<AdminEnrollment[]>([]);
const courses = ref<AdminCourse[]>([]);
const filterCourseId = ref('');

const dialogVisible = ref(false);
const formRef = ref<FormInstance>();
const form = reactive({
  course_id: '',
  student_no: '',
});
const rules: FormRules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  student_no: [{ required: true, message: '请输入学号', trigger: 'blur' }],
};

async function loadCourses() {
  try {
    courses.value = await adminApi.listCourses();
  } catch {
    /* http.ts 已 toast */
  }
}

async function load() {
  loading.value = true;
  try {
    list.value = await adminApi.listEnrollments(
      filterCourseId.value || undefined,
    );
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.course_id = '';
  form.student_no = '';
  dialogVisible.value = true;
}

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;
  submitting.value = true;
  try {
    await adminApi.createEnrollment({
      course_id: form.course_id,
      student_no: form.student_no,
    });
    ElMessage.success('选课记录已创建');
    dialogVisible.value = false;
    await load();
  } catch {
    /* http.ts 已 toast */
  } finally {
    submitting.value = false;
  }
}

async function handleDelete(row: AdminEnrollment) {
  try {
    await adminApi.deleteEnrollment(row.id);
    ElMessage.success('已退选');
    await load();
  } catch {
    /* http.ts 已 toast */
  }
}

onMounted(async () => {
  await Promise.all([loadCourses(), load()]);
});
</script>

<style scoped lang="scss">
.admin-enrollments {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-title {
  font-weight: 600;
}
</style>
