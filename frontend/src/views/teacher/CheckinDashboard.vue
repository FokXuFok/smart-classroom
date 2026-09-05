<template>
  <div class="checkin-dashboard" v-loading="loading">
    <div class="dashboard-header">
      <el-button text @click="router.back()">← 返回</el-button>
      <span class="session-title">
        {{ session?.course_name || '签到' }} 看板
      </span>
      <el-tag :type="session?.status === 1 ? 'success' : 'info'">
        {{ session?.status === 1 ? '进行中' : '已结束' }}
      </el-tag>
      <div class="header-actions">
        <el-button
          v-if="session?.status === 1"
          type="danger"
          :loading="ending"
          @click="onEnd"
        >
          结束签到
        </el-button>
        <el-button @click="onExport">导出 Excel</el-button>
      </div>
    </div>

    <div class="stat-cards">
      <StatCard title="选课人数" :value="stats.enrolled" color="blue" />
      <StatCard title="已签到" :value="signedCount" color="green" />
      <StatCard title="迟到" :value="lateCount" color="amber" />
      <StatCard title="待复核" :value="stats.reviewPending" color="purple" />
    </div>

    <el-card class="feed-card">
      <template #header><span class="card-title">实时动态(SSE)</span></template>
      <div class="feed-list">
        <div v-if="feed.length === 0" class="feed-empty">等待学生签到...</div>
        <div v-for="(f, i) in feed" :key="i" class="feed-item">
          <span class="feed-time">{{ f.time }}</span>
          <span class="feed-text">{{ f.text }}</span>
        </div>
      </div>
    </el-card>

    <el-card class="students-card">
      <template #header><span class="card-title">学生签到列表</span></template>
      <el-table :data="students" stripe>
        <el-table-column prop="student_no" label="学号" width="120" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="签到时间" width="100">
          <template #default="{ row }">
            {{ row.check_in_time ? fmtTime(row.check_in_time, 'HH:mm:ss') : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="相似度" width="100">
          <template #default="{ row }">
            {{ row.similarity1 != null ? row.similarity1.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="距签到点" width="110">
          <template #default="{ row }">
            {{ row.distance_hint != null ? row.distance_hint + ' 米' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="review_remark" label="备注" min-width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <template v-if="row.review_status === 1 && row.record_id">
              <el-button
                size="small"
                type="success"
                @click="onReview(row.record_id, 'approve', row.name)"
              >
                通过
              </el-button>
              <el-button
                size="small"
                type="danger"
                @click="onReview(row.record_id, 'reject', row.name)"
              >
                驳回
              </el-button>
            </template>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { teacherApi } from '@/api/teacher';
import { useCheckinStream } from '@/composables/useCheckinStream';
import { useDownload } from '@/composables/useDownload';
import { fmtTime } from '@/utils/format';
import StatCard from '@/components/StatCard.vue';
import type { CheckinSession, DashboardStudent } from '@/api/types';

const route = useRoute();
const router = useRouter();
const { download } = useDownload();
const sessionId = Number(route.params.sessionId);

const loading = ref(true);
const ending = ref(false);
const session = ref<CheckinSession | null>(null);
const students = ref<DashboardStudent[]>([]);
const feed = ref<{ time: string; text: string }[]>([]);

const stats = reactive({ enrolled: 0, reviewPending: 0 });

const signedCount = computed(
  () =>
    students.value.filter((s) => s.status === '正常' || s.status === '迟到')
      .length,
);
const lateCount = computed(
  () => students.value.filter((s) => s.status === '迟到').length,
);

function statusTagType(status: string) {
  if (status === '正常') return 'success';
  if (status === '迟到') return 'warning';
  if (status === '缺勤' || status === '未签到') return 'danger';
  return 'info';
}

async function loadDashboard() {
  loading.value = true;
  try {
    const data = await teacherApi.dashboard(sessionId);
    session.value = data.session;
    students.value = data.students;
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

function addFeed(text: string) {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  feed.value.unshift({ time, text });
  if (feed.value.length > 50) feed.value.pop();
}

// SSE 实时推送
useCheckinStream(sessionId, {
  onSnapshot: (e) => {
    stats.enrolled = e.enrolled;
    stats.reviewPending = e.review_pending;
    if (e.session_status === 0 && session.value) session.value.status = 0;
    addFeed(`快照:选课 ${e.enrolled} 人,待复核 ${e.review_pending} 条`);
  },
  onCheckin: (e) => {
    addFeed(
      `${e.name}(${e.student_no}) 签到 ${e.status_cn},相似度 ${e.similarity}`,
    );
    const s = students.value.find((x) => x.student_no === e.student_no);
    if (s) {
      s.status = e.status_cn;
      s.check_in_time = e.check_in_time;
      s.similarity1 = e.similarity;
    }
  },
  onReview: (e) => {
    addFeed(`${e.name}(${e.student_no}) 相似度不足,待复核`);
    stats.reviewPending++;
  },
  onReviewDone: (e) => {
    addFeed(`审核完成:${e.student_id} → ${e.status_cn}`);
    if (stats.reviewPending > 0) stats.reviewPending--;
    loadDashboard();
  },
  onSessionEnd: (e) => {
    addFeed(`会话已结束,补缺勤 ${e.absent_created} 条`);
    if (session.value) session.value.status = 0;
    loadDashboard();
  },
});

async function onEnd() {
  try {
    await ElMessageBox.confirm('确定结束签到?', '提示', { type: 'warning' });
  } catch {
    return;
  }
  ending.value = true;
  try {
    const r = await teacherApi.endCheckin(sessionId);
    ElMessage.success(`已结束,补缺勤 ${r.absent_created || 0} 条`);
  } catch {
    /* ignore */
  } finally {
    ending.value = false;
  }
}

async function onReview(
  recordId: number,
  action: 'approve' | 'reject',
  name: string,
) {
  try {
    const { value: remark } = await ElMessageBox.prompt(
      action === 'approve' ? `通过 ${name} 的签到(备注可选)` : `驳回 ${name} 的签到(原因可选)`,
      action === 'approve' ? '通过审核' : '驳回审核',
      { inputType: 'text', inputPlaceholder: '备注' },
    );
    await teacherApi.reviewAttendance(recordId, {
      action,
      remark: remark || '',
    });
    ElMessage.success('审核完成');
  } catch {
    // 用户取消或请求失败(http.ts 已 toast)
  }
}

function onExport() {
  download(teacherApi.exportUrl(sessionId));
}

onMounted(loadDashboard);
</script>

<style scoped lang="scss">
.checkin-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.dashboard-header {
  display: flex;
  align-items: center;
  gap: 12px;
  .session-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
  }
  .header-actions {
    margin-left: auto;
    display: flex;
    gap: 8px;
  }
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.feed-list {
  max-height: 200px;
  overflow-y: auto;
  .feed-empty {
    text-align: center;
    color: var(--text-sub);
    padding: 16px;
  }
  .feed-item {
    padding: 6px 0;
    border-bottom: 1px dashed var(--border);
    &:last-child { border-bottom: none; }
    .feed-time {
      color: var(--muted);
      font-family: monospace;
      font-size: 12px;
      margin-right: 12px;
    }
  }
}
.muted {
  color: var(--text-sub);
}
.card-title {
  font-weight: 600;
}
</style>
