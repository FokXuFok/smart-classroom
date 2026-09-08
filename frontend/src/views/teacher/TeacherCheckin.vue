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
          <el-button :loading="geoLoading" @click="locate">采集定位</el-button>
          <el-button @click="mapVisible = true">地图选点</el-button>
          <span v-if="form.lat && form.lng" class="coord">
            {{ form.lat.toFixed(6) }}, {{ form.lng.toFixed(6) }}
          </span>
          <el-checkbox v-model="useDefault" class="default-check">
            使用默认坐标(定位不可用时)
          </el-checkbox>
          <div v-if="geoError" class="error-text">{{ geoError }}</div>
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
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showQr(row)">二维码</el-button>
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

    <!-- 地图选点 -->
    <MapPicker
      v-model="mapVisible"
      :init-lat="form.lat ?? undefined"
      :init-lng="form.lng ?? undefined"
      @picked="onMapPicked"
    />

    <!-- 签到二维码（投影到大屏，学生拍照时须拍入画面） -->
    <el-dialog v-model="qrVisible" title="签到二维码（请投影到屏幕）" width="420px" append-to-body>
      <div class="qr-body">
        <img v-if="qrSessionId" :src="qrSrc" alt="签到二维码" class="qr-img" @error="onQrError" />
        <p v-if="qrLoadFailed" class="qr-err">二维码加载失败，请检查后端二维码组件（pip install qrcode）</p>
        <p class="qr-hint">
          每次发起签到都会生成新的二维码。学生签到拍照时，需将本二维码与本人脸部一起拍入画面，后端会从照片中解码比对。
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="qrVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { teacherApi } from '@/api/teacher';
import { useGeolocation, ACCURACY_LIMIT_M } from '@/composables/useGeolocation';
import MapPicker from '@/components/MapPicker.vue';
import { fmtTime } from '@/utils/format';
import type { Course, CheckinSession } from '@/api/types';

const router = useRouter();
const { loading: geoLoading, error: geoError, getPosition } = useGeolocation();

const courses = ref<Course[]>([]);
const coursesLoading = ref(false);
const sessions = ref<CheckinSession[]>([]);
const sessionsLoading = ref(false);
const starting = ref(false);
const endingId = ref<number | null>(null);
const useDefault = ref(false);
const mapVisible = ref(false);

// 签到二维码弹窗
const qrVisible = ref(false);
const qrSessionId = ref<number | null>(null);
const qrLoadFailed = ref(false);
const qrSrc = computed(() => {
  if (!qrSessionId.value) return '';
  // ?t= 防止浏览器缓存旧二维码
  return `/api/teacher/checkin/${qrSessionId.value}/qr?t=${Date.now()}`;
});

const form = reactive({
  course_id: '',
  duration_minutes: 5,
  range_meters: 200,
  lat: undefined as number | undefined,
  lng: undefined as number | undefined,
});

// 地图选点成功 → 使用该坐标，关闭"默认坐标"兜底
function onMapPicked(pos: { lat: number; lng: number }) {
  form.lat = pos.lat;
  form.lng = pos.lng;
  useDefault.value = false;
  ElMessage.success(
    `已选点: ${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)}，将作为签到中心`,
  );
}

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
  const pos = await getPosition();
  if (pos) {
    if (pos.accuracy > ACCURACY_LIMIT_M) {
      // IP 定位等低精度源：坐标误差可达公里级，不能作为围栏基准
      useDefault.value = true;
      ElMessage.warning(
        `定位精度不足(${Math.round(pos.accuracy)}m),本次将使用默认坐标`,
      );
      return;
    }
    form.lat = pos.lat;
    form.lng = pos.lng;
    useDefault.value = false;
    ElMessage.success(
      `定位成功: ${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)} (精度${Math.round(pos.accuracy)}m)`,
    );
  } else {
    ElMessage.warning(geoError.value || '定位失败,将使用默认坐标');
  }
}

async function onStart() {
  if (!form.course_id) {
    ElMessage.warning('请选择课程');
    return;
  }
  // 未勾选默认坐标但没采集到定位 → 自动先尝试采集
  if (!useDefault.value && !form.lat && !form.lng) {
    ElMessage.info('正在自动采集定位…');
    const pos = await getPosition();
    if (pos && pos.accuracy <= ACCURACY_LIMIT_M) {
      form.lat = pos.lat;
      form.lng = pos.lng;
    } else {
      useDefault.value = true; // 采集失败或精度不足自动降级默认坐标
      ElMessage.warning(
        pos
          ? `定位精度不足(${Math.round(pos.accuracy)}m),本次使用默认坐标`
          : geoError.value || '定位失败,本次使用默认坐标',
      );
    }
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
    // 发起成功后弹出二维码（每次签到 token 均不同，供学生拍照核验）
    qrSessionId.value = data.id;
    qrLoadFailed.value = false;
    qrVisible.value = true;
    await loadSessions();
  } catch {
    /* http.ts 已 toast */
  } finally {
    starting.value = false;
  }
}

// 查看某个会话的二维码（可再次投影）
function showQr(row: CheckinSession) {
  qrSessionId.value = row.id;
  qrLoadFailed.value = false;
  qrVisible.value = true;
}

function onQrError() {
  qrLoadFailed.value = true;
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
.qr-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.qr-img {
  width: 320px;
  height: 320px;
  border: 1px solid var(--border);
  border-radius: 8px;
}
.qr-err {
  color: var(--absent);
  font-size: 13px;
}
.qr-hint {
  color: var(--text-sub);
  font-size: 13px;
  line-height: 1.6;
  text-align: center;
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
