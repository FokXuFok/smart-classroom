<template>
  <div class="teacher-checkin">
    <el-card class="form-card">
      <template #header><span class="card-title">发起签到</span></template>
      <el-form :model="form" label-width="100px">
        <el-form-item label="课程">
          <el-select
            v-model="form.course_id"
            placeholder="选择课程"
            :loading="coursesLoading"
            style="width: 320px"
          >
            <el-option
              v-for="c in courses"
              :key="c.course_id"
              :label="`${c.course_id} ${c.course_name}`"
              :value="c.course_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="签到时长">
          <el-input-number v-model="form.duration_minutes" :min="1" :max="180" />
          <span class="unit">分钟</span>
        </el-form-item>
        <el-form-item label="围栏范围">
          <el-input-number v-model="form.range_meters" :min="50" :max="2000" :step="50" />
          <span class="unit">米</span>
        </el-form-item>
        <el-form-item label="签到定位">
          <el-button :loading="geo.loading" @click="locate">采集定位</el-button>
          <span v-if="form.lat && form.lng" class="coord">
            {{ form.lat.toFixed(6) }}, {{ form.lng.toFixed(6) }}
          </span>
          <el-checkbox v-model="useDefault" class="default-check">
            使用默认坐标(定位不可用时)
          </el-checkbox>
          <div v-if="geo.error" class="error-text">{{ geo.error }}</div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="starting" @click="onStart">
            发起签到
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="list-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">签到会话</span>
          <el-button text @click="loadSessions">刷新</el-button>
        </div>
      </template>
      <el-table :data="sessions" v-loading="sessionsLoading" stripe>
        <el-table-column prop="course_name" label="课程" min-width="160" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '进行中' : '已结束' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="signed_count" label="已签" width="80" />
        <el-table-column prop="range_meters" label="围栏(米)" width="100" />
        <el-table-column prop="duration_minutes" label="时长(分)" width="100" />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="goDashboard(row.id)">
              看板
            </el-button>
            <el-button
              v-if="row.status === 1"
              size="small"
              type="danger"
              :loading="endingId === row.id"
              @click="onEnd(row.id)"
            >
              结束
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { teacherApi } from '@/api/teacher';
import { useGeolocation } from '@/composables/useGeolocation';
import { fmtTime } from '@/utils/format';
import type { Course, CheckinSession } from '@/api/types';

const router = useRouter();
const geo = useGeolocation();

const courses = ref<Course[]>([]);
const coursesLoading = ref(false);
const sessions = ref<CheckinSession[]>([]);
const sessionsLoading = ref(false);
const starting = ref(false);
const endingId = ref<number | null>(null);
const useDefault = ref(false);

const form = reactive({
  course_id: '',
  duration_minutes: 5,
  range_meters: 200,
  lat: undefined as number | undefined,
  lng: undefined as number | undefined,
});

async function loadCourses() {
  coursesLoading.value = true;
  try {
    courses.value = await teacherApi.myCourses();
  } catch {
    /* http.ts 已 toast */
  } finally {
    coursesLoading.value = false;
  }
}

async function loadSessions() {
  sessionsLoading.value = true;
  try {
    sessions.value = await teacherApi.listSessions();
  } catch {
    /* ignore */
  } finally {
    sessionsLoading.value = false;
  }
}

async function locate() {
  const pos = await geo.getPosition();
  if (pos) {
    form.lat = pos.lat;
    form.lng = pos.lng;
    useDefault.value = false;
  }
}

async function onStart() {
  if (!form.course_id) {
    ElMessage.warning('请选择课程');
    return;
  }
  const lat = useDefault.value ? undefined : form.lat;
  const lng = useDefault.value ? undefined : form.lng;
  starting.value = true;
  try {
    const data = await teacherApi.startCheckin({
      course_id: form.course_id,
      lat,
      lng,
      range_meters: form.range_meters,
      duration_minutes: form.duration_minutes,
    });
    ElMessage.success(`签到已发起${data.used_default ? '(默认坐标)' : ''}`);
    await loadSessions();
    router.push(`/teacher/checkin/${data.id}`);
  } catch {
    /* http.ts 已 toast */
  } finally {
    starting.value = false;
  }
}

async function onEnd(id: number) {
  try {
    await ElMessageBox.confirm(
      '确定结束签到?未签学生将记为缺勤',
      '提示',
      { type: 'warning' },
    );
  } catch {
    return;
  }
  endingId.value = id;
  try {
    const result = await teacherApi.endCheckin(id);
    ElMessage.success(`签到已结束,补缺勤 ${result.absent_created || 0} 条`);
    await loadSessions();
  } catch {
    /* ignore */
  } finally {
    endingId.value = null;
  }
}

function goDashboard(id: number) {
  router.push(`/teacher/checkin/${id}`);
}

onMounted(() => {
  loadCourses();
  loadSessions();
});
</script>

<style scoped lang="scss">
.teacher-checkin {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.unit {
  margin-left: 8px;
  color: var(--text-sub);
}
.coord {
  margin-left: 12px;
  color: var(--blue-deep);
  font-family: monospace;
}
.default-check {
  margin-left: 16px;
}
.error-text {
  color: var(--absent);
  font-size: 12px;
  margin-top: 4px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-weight: 600;
}
</style>
