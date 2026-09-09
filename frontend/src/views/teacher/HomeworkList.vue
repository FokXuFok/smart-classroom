<template>
  <div class="homework-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-title">作业管理</span>
          <div class="header-actions">
            <el-select
              v-model="courseFilter"
              placeholder="全部课程"
              clearable
              :loading="coursesLoading"
              style="width: 220px"
              @change="load"
            >
              <el-option
                v-for="c in courses"
                :key="c.course_id"
                :label="`${c.course_id} ${c.course_name}`"
                :value="c.course_id"
              />
            </el-select>
            <el-button type="primary" @click="router.push('/teacher/homework/new')">
              新建作业
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="title" label="作业标题" min-width="160" />
        <el-table-column prop="course_id" label="课程" width="100" />
        <el-table-column prop="programming_language" label="语言" width="80" />
        <el-table-column prop="max_score" label="满分" width="80" />
        <el-table-column label="截止时间" width="160">
          <template #default="{ row }">
            {{ row.deadline ? fmtTime(row.deadline) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="test_case_count" label="用例数" width="80" />
        <el-table-column label="提交" width="100">
          <template #default="{ row }">
            {{ row.submit_count }}/{{ row.student_count }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              link
              @click="router.push(`/teacher/homework/${row.id}`)"
            >
              编辑
            </el-button>
            <el-button
              size="small"
              type="success"
              :loading="gradingId === row.id"
              @click="onAiGrade(row.id)"
            >
              AI 批改
            </el-button>
            <el-dropdown
              trigger="click"
              @command="(cmd: string) => onMore(cmd, row as Homework)"
            >
              <el-button size="small" link type="primary">
                更多<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="similarity">查重</el-dropdown-item>
                  <el-dropdown-item command="rejudge">重评</el-dropdown-item>
                  <el-dropdown-item command="export">导出成绩册</el-dropdown-item>
                  <el-dropdown-item divided command="subs">查看提交列表</el-dropdown-item>
                  <el-dropdown-item command="gradebook">查看成绩册</el-dropdown-item>
                  <el-dropdown-item
                    divided
                    command="openFeedback"
                    :disabled="row.feedback_visible === 1"
                  >
                    {{ row.feedback_visible === 1 ? '已开放AI反馈' : '开放AI反馈给学生' }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button
              size="small"
              type="danger"
              link
              :loading="deletingId === row.id"
              @click="onDelete(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 提交列表弹窗 -->
    <el-dialog
      v-model="subsDialog"
      :title="`提交列表 · ${subsDialogTitle}`"
      width="920px"
      destroy-on-close
    >
      <el-table :data="subsData" v-loading="subsLoading" stripe height="480">
        <el-table-column prop="student_id" label="学号" width="120" />
        <el-table-column label="姓名" width="110">
          <template #default="{ row }">{{ row.student_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 2 ? 'success' : row.status === 1 ? 'primary' : 'warning'"
            >
              {{ row.status_cn || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="得分" width="80">
          <template #default="{ row }">{{ row.score ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="提交时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.submit_time) }}</template>
        </el-table-column>
        <el-table-column label="评测结果 / AI 反馈" min-width="260">
          <template #default="{ row }">
            <div v-if="row.compile_error" class="err-line">
              <el-tag size="small" type="danger">编译错误</el-tag>
              <div class="err-text">{{ row.compile_error }}</div>
            </div>
            <div v-else class="err-line">
              <span class="feedback">{{ row.ai_feedback || '（暂无 AI 反馈，可在列表点"AI 批改"生成）' }}</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 成绩册弹窗 -->
    <el-dialog
      v-model="gradeDialog"
      :title="`成绩册 · ${gradeDialogTitle}`"
      width="760px"
      destroy-on-close
    >
      <el-table :data="gradeData" v-loading="gradeLoading" stripe height="480">
        <el-table-column prop="student_id" label="学号" width="140" />
        <el-table-column label="姓名" width="130">
          <template #default="{ row }">{{ row.student_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="得分" width="100">
          <template #default="{ row }">
            <b>{{ row.score ?? '-' }}</b>
          </template>
        </el-table-column>
        <el-table-column prop="submit_count" label="提交次数" width="110" />
        <el-table-column label="评测时间" min-width="160">
          <template #default="{ row }">{{ fmtTime(row.judge_time) || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ArrowDown } from '@element-plus/icons-vue';
import { homeworkApi } from '@/api/homework';
import { aiApi } from '@/api/ai';
import { teacherApi } from '@/api/teacher';
import { useDownload } from '@/composables/useDownload';
import { fmtTime } from '@/utils/format';
import type { Course, Homework, Submission, GradeBookRow } from '@/api/types';

const router = useRouter();
const { download } = useDownload();

const courses = ref<Course[]>([]);
const coursesLoading = ref(false);
const list = ref<Homework[]>([]);
const loading = ref(false);
const courseFilter = ref('');
const deletingId = ref<number | null>(null);
const gradingId = ref<number | null>(null);

// 提交列表 / 成绩册 弹窗状态
const subsDialog = ref(false);
const subsDialogTitle = ref('');
const subsData = ref<Submission[]>([]);
const subsLoading = ref(false);
const gradeDialog = ref(false);
const gradeDialogTitle = ref('');
const gradeData = ref<GradeBookRow[]>([]);
const gradeLoading = ref(false);

async function loadCourses() {
  coursesLoading.value = true;
  try {
    courses.value = await teacherApi.myCourses();
  } catch {
    /* ignore */
  } finally {
    coursesLoading.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    list.value = await homeworkApi.list(courseFilter.value);
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

async function onSimilarity(id: number) {
  try {
    const r: any = await homeworkApi.similarity(id);
    ElMessage.success(`查重完成,命中 ${r.length} 对疑似抄袭`);
  } catch {
    /* ignore */
  }
}

async function onRejudge(id: number) {
  try {
    await ElMessageBox.confirm('确定重评所有提交?', '提示', { type: 'warning' });
  } catch {
    return;
  }
  try {
    const r: any = await homeworkApi.rejudge(id);
    ElMessage.success(`重评任务已提交,共 ${r.rejudge_count} 条`);
  } catch {
    /* ignore */
  }
}

function onExport(id: number) {
  download(homeworkApi.gradebookExportUrl(id));
}

async function onAiGrade(id: number) {
  try {
    await ElMessageBox.confirm(
      'AI 批改会对已评测提交生成反馈(单次最多 20 条,可能需 1-2 分钟),继续?',
      'AI 批改',
      { type: 'warning' },
    );
  } catch {
    return;
  }
  gradingId.value = id;
  try {
    const r: any = await aiApi.gradeAll(id);
    ElMessage.success(
      `AI 批改完成:成功 ${r.graded},降级 ${r.degraded},失败 ${r.failed}`,
    );
    await load();
  } catch {
    /* http.ts 已 toast */
  } finally {
    gradingId.value = null;
  }
}

// ---------- "更多"下拉操作 ----------

async function onMore(cmd: string, row: Homework) {
  if (cmd === 'similarity') {
    await onSimilarity(row.id);
  } else if (cmd === 'rejudge') {
    await onRejudge(row.id);
  } else if (cmd === 'export') {
    onExport(row.id);
  } else if (cmd === 'subs') {
    openSubs(row);
  } else if (cmd === 'gradebook') {
    openGradebook(row);
  } else if (cmd === 'openFeedback') {
    await onOpenFeedback(row.id);
  }
}

// 查看提交列表(学生提交记录/评测结果/AI反馈)
async function openSubs(row: Homework) {
  subsDialogTitle.value = row.title;
  subsDialog.value = true;
  subsData.value = [];
  subsLoading.value = true;
  try {
    subsData.value = await homeworkApi.submissions(row.id);
  } catch {
    /* http.ts 已 toast */
  } finally {
    subsLoading.value = false;
  }
}

// 查看成绩册
async function openGradebook(row: Homework) {
  gradeDialogTitle.value = row.title;
  gradeDialog.value = true;
  gradeData.value = [];
  gradeLoading.value = true;
  try {
    gradeData.value = await homeworkApi.gradebook(row.id);
  } catch {
    /* http.ts 已 toast */
  } finally {
    gradeLoading.value = false;
  }
}

// 提前向学生开放 AI 批改反馈
async function onOpenFeedback(id: number) {
  try {
    await ElMessageBox.confirm(
      '开放后学生可在提交详情中立即查看 AI 批改反馈(通常截止后才可见),继续?',
      '开放 AI 反馈',
      { type: 'warning' },
    );
  } catch {
    return;
  }
  try {
    await homeworkApi.openFeedback(id);
    ElMessage.success('AI 反馈已提前开放');
    await load();
  } catch {
    /* http.ts 已 toast */
  }
}

async function onDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该作业?', '提示', { type: 'warning' });
  } catch {
    return;
  }
  deletingId.value = id;
  try {
    await homeworkApi.delete(id);
    ElMessage.success('作业已删除');
    await load();
  } catch {
    /* http.ts 已 toast(有提交记录拒绝) */
  } finally {
    deletingId.value = null;
  }
}

onMounted(() => {
  loadCourses();
  load();
});
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.card-title {
  font-weight: 600;
}
.err-line {
  line-height: 1.6;
}
.err-text {
  font-size: 12px;
  color: #dc2626;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 72px;
  overflow: auto;
}
.feedback {
  font-size: 12.5px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #334155;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
