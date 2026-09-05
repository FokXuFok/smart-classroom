<template>
  <div class="checkin-review">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-title">待复核审核</span>
          <el-button text :loading="loading" @click="loadAll">刷新</el-button>
        </div>
      </template>
      <el-empty v-if="!loading && records.length === 0" description="暂无待复核记录" />
      <el-table v-else :data="records" v-loading="loading" stripe>
        <el-table-column prop="course_name" label="课程" width="140" />
        <el-table-column prop="student_no" label="学号" width="120" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="status" label="状态" width="80" />
        <el-table-column label="相似度" width="100">
          <template #default="{ row }">
            {{ row.similarity1 != null ? row.similarity1.toFixed(4) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="review_remark" label="备注" min-width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.record_id"
              size="small"
              type="success"
              @click="onReview(row, 'approve')"
            >
              通过
            </el-button>
            <el-button
              v-if="row.record_id"
              size="small"
              type="danger"
              @click="onReview(row, 'reject')"
            >
              驳回
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { teacherApi } from '@/api/teacher';
import type { DashboardStudent, CheckinSession } from '@/api/types';

interface ReviewRow extends DashboardStudent {
  course_name: string;
  session_id: number;
}

const loading = ref(false);
const records = ref<ReviewRow[]>([]);

async function loadAll() {
  loading.value = true;
  try {
    const sessions: CheckinSession[] = await teacherApi.listSessions();
    // 只查进行中(可能有待复核),已结束的会话也可能有待复核,这里全部查
    const activeSessions = sessions.filter((s) => s.status === 1);
    const all: ReviewRow[] = [];
    await Promise.all(
      activeSessions.map(async (s) => {
        try {
          const data = await teacherApi.dashboard(s.id);
          data.students
            .filter((st) => st.review_status === 1 && st.record_id)
            .forEach((st) => {
              all.push({
                ...st,
                course_name: data.session.course_id,
                session_id: s.id,
              });
            });
        } catch {
          /* ignore single session */
        }
      }),
    );
    records.value = all;
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

async function onReview(row: ReviewRow, action: 'approve' | 'reject') {
  if (!row.record_id) return;
  try {
    const { value: remark } = await ElMessageBox.prompt(
      action === 'approve'
        ? `通过 ${row.name} 的签到(备注可选)`
        : `驳回 ${row.name} 的签到(原因可选)`,
      action === 'approve' ? '通过审核' : '驳回审核',
      { inputType: 'text', inputPlaceholder: '备注' },
    );
    await teacherApi.reviewAttendance(row.record_id, {
      action,
      remark: remark || '',
    });
    ElMessage.success('审核完成');
    // 从列表移除
    records.value = records.value.filter((r) => r.record_id !== row.record_id);
  } catch {
    // 用户取消或失败
  }
}

onMounted(loadAll);
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-weight: 600;
}
</style>
