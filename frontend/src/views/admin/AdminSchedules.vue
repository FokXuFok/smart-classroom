<template>
  <div class="admin-schedules" v-loading="loading">
    <el-card>
      <template #header>
        <div class="header-bar">
          <span class="card-title">课表管理</span>
          <div class="header-actions">
            <el-select
              v-model="filterClassId"
              placeholder="全部班级"
              clearable
              style="width: 200px"
              @change="load"
            >
              <el-option label="全部班级" value="" />
              <el-option
                v-for="c in classes"
                :key="c.class_id"
                :label="`${c.class_id} - ${c.class_name}`"
                :value="c.class_id"
              />
            </el-select>
            <el-select
              v-model="filterWeekday"
              placeholder="全部星期"
              clearable
              style="width: 140px"
              @change="load"
            >
              <el-option label="全部星期" value="" />
              <el-option
                v-for="w in 7"
                :key="w"
                :label="weekdayText(w)"
                :value="w"
              />
            </el-select>
            <el-button @click="load">刷新</el-button>
            <el-button type="primary" @click="openCreate">新增排课</el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" border stripe>
        <el-table-column label="星期" width="100">
          <template #default="{ row }">{{ weekdayText(row.weekday) }}</template>
        </el-table-column>
        <el-table-column label="节次" width="160">
          <template #default="{ row }">
            {{ row.start_time }} - {{ row.end_time }}
          </template>
        </el-table-column>
        <el-table-column label="课程" min-width="160">
          <template #default="{ row }">
            {{ row.course_name || row.course_id }}
          </template>
        </el-table-column>
        <el-table-column label="班级" min-width="140">
          <template #default="{ row }">
            {{ row.class_name || row.class_id }}
          </template>
        </el-table-column>
        <el-table-column label="周次" width="120">
          <template #default="{ row }">{{ row.weeks || '-' }}</template>
        </el-table-column>
        <el-table-column label="教室" width="140">
          <template #default="{ row }">{{ row.classroom || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              title="确定删除该排课记录吗？"
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

    <el-dialog v-model="dialogVisible" title="新增排课" width="520px">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="90px"
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
        <el-form-item label="班级" prop="class_id">
          <el-select
            v-model="form.class_id"
            placeholder="请选择班级"
            style="width: 100%"
          >
            <el-option
              v-for="c in classes"
              :key="c.class_id"
              :label="`${c.class_id} - ${c.class_name}`"
              :value="c.class_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="星期" prop="weekday">
          <el-select
            v-model="form.weekday"
            placeholder="请选择星期"
            style="width: 100%"
          >
            <el-option
              v-for="w in 7"
              :key="w"
              :label="weekdayText(w)"
              :value="w"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-time-select
            v-model="form.start_time"
            :max-time="form.end_time"
            placeholder="起始时间"
            start="08:00"
            step="00:05"
            end="22:00"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_time">
          <el-time-select
            v-model="form.end_time"
            :min-time="form.start_time"
            placeholder="结束时间"
            start="08:00"
            step="00:05"
            end="22:00"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="周次" prop="weeks">
          <el-input v-model="form.weeks" placeholder="如 1-16" />
        </el-form-item>
        <el-form-item label="教室" prop="classroom">
          <el-input v-model="form.classroom" placeholder="如 教三-301" />
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
import type { AdminSchedule, AdminCourse, AdminClass } from '@/api/types';

const loading = ref(false);
const submitting = ref(false);
const list = ref<AdminSchedule[]>([]);
const courses = ref<AdminCourse[]>([]);
const classes = ref<AdminClass[]>([]);
const filterClassId = ref('');
const filterWeekday = ref<number | ''>('');

const dialogVisible = ref(false);
const formRef = ref<FormInstance>();
const form = reactive({
  course_id: '',
  class_id: '',
  weekday: 1 as number,
  start_time: '',
  end_time: '',
  weeks: '1-16',
  classroom: '',
});
const rules: FormRules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  class_id: [{ required: true, message: '请选择班级', trigger: 'change' }],
  weekday: [{ required: true, message: '请选择星期', trigger: 'change' }],
  start_time: [
    { required: true, message: '请选择开始时间', trigger: 'change' },
  ],
  end_time: [
    { required: true, message: '请选择结束时间', trigger: 'change' },
  ],
};

function weekdayText(w: number): string {
  return ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][w - 1] || String(w);
}

async function loadOptions() {
  try {
    const [c, cls] = await Promise.all([
      adminApi.listCourses(),
      adminApi.listClasses(),
    ]);
    courses.value = c;
    classes.value = cls;
  } catch {
    /* http.ts 已 toast */
  }
}

async function load() {
  loading.value = true;
  try {
    list.value = await adminApi.listSchedules({
      class_id: filterClassId.value || undefined,
      weekday:
        typeof filterWeekday.value === 'number'
          ? filterWeekday.value
          : undefined,
    });
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  form.course_id = '';
  form.class_id = '';
  form.weekday = 1;
  form.start_time = '';
  form.end_time = '';
  form.weeks = '1-16';
  form.classroom = '';
  dialogVisible.value = true;
}

async function handleCreate() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;
  submitting.value = true;
  try {
    await adminApi.createSchedule({
      course_id: form.course_id,
      class_id: form.class_id,
      weekday: form.weekday,
      start_time: form.start_time,
      end_time: form.end_time,
      weeks: form.weeks || undefined,
      classroom: form.classroom || undefined,
    });
    ElMessage.success('排课已创建');
    dialogVisible.value = false;
    await load();
  } catch {
    /* http.ts 已 toast */
  } finally {
    submitting.value = false;
  }
}

async function handleDelete(row: AdminSchedule) {
  try {
    await adminApi.deleteSchedule(row.id);
    ElMessage.success('已删除');
    await load();
  } catch {
    /* http.ts 已 toast */
  }
}

onMounted(async () => {
  await Promise.all([loadOptions(), load()]);
});
</script>

<style scoped lang="scss">
.admin-schedules {
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
