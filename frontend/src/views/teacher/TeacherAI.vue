<template>
  <div class="teacher-ai">
    <el-tabs v-model="active" class="ai-tabs">
      <!-- 1. AI 备课助手 -->
      <el-tab-pane label="AI 备课助手" name="assist">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-title">备课助手 Agent</span>
              <span class="light">输入主题,AI 生成「课堂提问 / 知识点解析 / 易错点提醒」</span>
            </div>
          </template>
          <div class="row">
            <el-select
              v-model="assistCourseId"
              placeholder="选择课程"
              style="width: 240px"
              :loading="coursesLoading"
            >
              <el-option
                v-for="c in courses"
                :key="c.course_id"
                :label="`${c.course_id} ${c.course_name}`"
                :value="c.course_id"
              />
            </el-select>
            <el-input
              v-model="assistTopic"
              placeholder="备课主题,如:数组与指针的关系"
              style="flex: 1; min-width: 280px"
              @keyup.enter="onAssist"
            />
            <el-button
              type="primary"
              :loading="assistLoading"
              :disabled="!assistCourseId || !assistTopic.trim()"
              @click="onAssist"
            >
              生成备课材料
            </el-button>
          </div>
          <pre class="out">{{ assistResult || '输入主题后点击生成,备课材料将显示在这里...' }}</pre>
        </el-card>
      </el-tab-pane>

      <!-- 2. 答疑热词 -->
      <el-tab-pane label="答疑热词" name="hotwords">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-title">答疑热词统计</span>
              <span class="light">聚合本课学生提问,提取高频词</span>
            </div>
          </template>
          <div class="row">
            <el-select
              v-model="hotCourseId"
              placeholder="选择课程"
              style="width: 240px"
              :loading="coursesLoading"
              @change="onHotwords"
            >
              <el-option
                v-for="c in courses"
                :key="c.course_id"
                :label="`${c.course_id} ${c.course_name}`"
                :value="c.course_id"
              />
            </el-select>
            <el-button
              :loading="hotLoading"
              :disabled="!hotCourseId"
              @click="onHotwords"
            >
              查看热词
            </el-button>
          </div>
          <div v-if="hotwords.length" class="hotwords">
            <span
              v-for="w in hotwords"
              :key="w.word"
              class="hot-badge"
              :style="{ fontSize: hotFont(w.count) + 'px' }"
            >
              {{ w.word }}
              <em>×{{ w.count }}</em>
            </span>
          </div>
          <el-empty v-else-if="!hotLoading" description="暂无热词" />
        </el-card>
      </el-tab-pane>

      <!-- 3. 班级错误分析 -->
      <el-tab-pane label="班级错误分析" name="errors">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-title">错误分析 Agent</span>
              <span class="light">聚合本作业所有错误样本,生成「高频错误统计 + 讲评建议」</span>
            </div>
          </template>
          <div class="row">
            <el-select
              v-model="errCourseId"
              placeholder="按课程筛选作业"
              clearable
              style="width: 240px"
              :loading="coursesLoading"
              @change="loadHomeworks"
            >
              <el-option
                v-for="c in courses"
                :key="c.course_id"
                :label="`${c.course_id} ${c.course_name}`"
                :value="c.course_id"
              />
            </el-select>
            <el-select
              v-model="errHwId"
              placeholder="选择作业"
              style="flex: 1; min-width: 280px"
              :loading="hwLoading"
            >
              <el-option
                v-for="h in homeworks"
                :key="h.id"
                :label="`${h.title}（${h.programming_language}）`"
                :value="h.id"
              />
            </el-select>
            <el-button
              type="primary"
              :loading="errLoading"
              :disabled="!errHwId"
              @click="onAnalyze"
            >
              生成错误分析
            </el-button>
          </div>
          <div v-if="errReport" class="err-meta">
            <el-tag size="small">作业:{{ errReport.homework_title }}</el-tag>
            <el-tag size="small" type="info">语言:{{ errReport.language }}</el-tag>
            <el-tag size="small" type="warning">样本数:{{ errReport.sample_count }}</el-tag>
            <el-tag size="small" type="success">已评测提交:{{ errReport.submission_count }}</el-tag>
          </div>
          <pre class="out">{{ errReport?.report || '选择作业后点击生成,错误分析报告将显示在这里...' }}</pre>
        </el-card>
      </el-tab-pane>

      <!-- 4. 知识库管理 -->
      <el-tab-pane label="知识库管理" name="knowledge">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-title">课程知识库</span>
              <div class="header-actions">
                <el-select
                  v-model="kbCourseId"
                  placeholder="按课程筛选"
                  clearable
                  style="width: 220px"
                  @change="loadKnowledge"
                >
                  <el-option
                    v-for="c in courses"
                    :key="c.course_id"
                    :label="`${c.course_id} ${c.course_name}`"
                    :value="c.course_id"
                  />
                </el-select>
                <el-button type="primary" @click="openKbDialog()">新建知识点</el-button>
              </div>
            </div>
          </template>
          <el-table :data="knowledge" v-loading="kbLoading" stripe>
            <el-table-column prop="title" label="标题" min-width="160" />
            <el-table-column prop="course_id" label="课程" width="120">
              <template #default="{ row }">{{ row.course_id || '通用' }}</template>
            </el-table-column>
            <el-table-column prop="subject" label="科目" width="120" />
            <el-table-column prop="difficulty" label="难度" width="80" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                  {{ row.status === 1 ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openKbDialog(row as AiKnowledge)">编辑</el-button>
                <el-button
                  size="small"
                  type="danger"
                  :loading="kbDeleting === row.id"
                  @click="onDeleteKnowledge(row.id)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 5. 评分规则管理 -->
      <el-tab-pane label="评分规则" name="rules">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-title">评分规则</span>
              <div class="header-actions">
                <el-select
                  v-model="ruleCourseId"
                  placeholder="按课程筛选"
                  clearable
                  style="width: 220px"
                  @change="loadRules"
                >
                  <el-option
                    v-for="c in courses"
                    :key="c.course_id"
                    :label="`${c.course_id} ${c.course_name}`"
                    :value="c.course_id"
                  />
                </el-select>
                <el-button type="primary" @click="openRuleDialog()">新建规则</el-button>
              </div>
            </div>
          </template>
          <el-table :data="rules" v-loading="ruleLoading" stripe>
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column label="课程" width="120">
              <template #default="{ row }">{{ row.course_id || '通用' }}</template>
            </el-table-column>
            <el-table-column label="类型" width="110">
              <template #default="{ row }">
                <el-tag :type="row.rule_type === 'deduct' ? 'danger' : 'success'" size="small">
                  {{ row.rule_type === 'deduct' ? '扣分项' : '踩分点' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="weight" label="权重" width="80" />
            <el-table-column prop="max_score" label="满分" width="80" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
                  {{ row.status === 1 ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="openRuleDialog(row as AiRule)">编辑</el-button>
                <el-button
                  size="small"
                  type="danger"
                  :loading="ruleDeleting === row.id"
                  @click="onDeleteRule(row.id)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 知识点编辑对话框 -->
    <el-dialog
      v-model="kbDialog"
      :title="kbForm.id ? '编辑知识点' : '新建知识点'"
      width="640px"
      @closed="resetKbForm"
    >
      <el-form :model="kbForm" label-width="90px">
        <el-form-item label="课程" required>
          <el-select v-model="kbForm.course_id" placeholder="选择课程" style="width: 100%">
            <el-option
              v-for="c in courses"
              :key="c.course_id"
              :label="`${c.course_id} ${c.course_name}`"
              :value="c.course_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="kbForm.title" placeholder="知识点标题" />
        </el-form-item>
        <el-form-item label="科目">
          <el-input v-model="kbForm.subject" placeholder="如:数据结构 / Python 语法" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="kbForm.content"
            type="textarea"
            :rows="6"
            placeholder="知识点详细内容,会作为答疑与备课的上下文"
          />
        </el-form-item>
        <el-form-item label="难度">
          <el-input-number v-model="kbForm.difficulty" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="kbForm.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="kbForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kbDialog = false">取消</el-button>
        <el-button type="primary" :loading="kbSaving" @click="onSaveKnowledge">保存</el-button>
      </template>
    </el-dialog>

    <!-- 评分规则编辑对话框 -->
    <el-dialog
      v-model="ruleDialog"
      :title="ruleForm.id ? '编辑评分规则' : '新建评分规则'"
      width="640px"
      @closed="resetRuleForm"
    >
      <el-form :model="ruleForm" label-width="90px">
        <el-form-item label="课程">
          <el-select
            v-model="ruleForm.course_id"
            placeholder="留空 = 通用规则"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="c in courses"
              :key="c.course_id"
              :label="`${c.course_id} ${c.course_name}`"
              :value="c.course_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="ruleForm.name" placeholder="规则名称" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-radio-group v-model="ruleForm.rule_type">
            <el-radio value="score_point">踩分点</el-radio>
            <el-radio value="deduct">扣分项</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="ruleForm.content"
            type="textarea"
            :rows="4"
            placeholder="规则详细描述"
          />
        </el-form-item>
        <el-form-item label="权重">
          <el-input-number v-model="ruleForm.weight" :min="0" :step="0.1" />
        </el-form-item>
        <el-form-item label="满分">
          <el-input-number v-model="ruleForm.max_score" :min="0" />
        </el-form-item>
        <el-form-item label="评分标准">
          <el-input v-model="ruleForm.criteria" placeholder="评分标准描述" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="ruleForm.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="ruleForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialog = false">取消</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="onSaveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { aiApi } from '@/api/ai';
import { teacherApi } from '@/api/teacher';
import { homeworkApi } from '@/api/homework';
import type {
  Course,
  Homework,
  AiHotword,
  AiKnowledge,
  AiKnowledgePayload,
  AiRule,
  AiRulePayload,
  AiErrorReport,
} from '@/api/types';

const active = ref('assist');

// 课程下拉数据(所有子 Tab 共享)
const courses = ref<Course[]>([]);
const coursesLoading = ref(false);

// ====== 1. 备课助手 ======
const assistCourseId = ref('');
const assistTopic = ref('');
const assistResult = ref('');
const assistLoading = ref(false);

async function onAssist() {
  if (!assistCourseId.value || !assistTopic.value.trim()) return;
  assistLoading.value = true;
  assistResult.value = 'AI 备课生成中...(可能需要 10-30 秒)';
  try {
    const r = await aiApi.teacherAssist({
      course_id: assistCourseId.value,
      topic: assistTopic.value.trim(),
    });
    assistResult.value = r.content || '(空)';
  } catch {
    assistResult.value = '生成失败,请稍后重试';
  } finally {
    assistLoading.value = false;
  }
}

// ====== 2. 答疑热词 ======
const hotCourseId = ref('');
const hotwords = ref<AiHotword[]>([]);
const hotLoading = ref(false);

async function onHotwords() {
  if (!hotCourseId.value) return;
  hotLoading.value = true;
  try {
    hotwords.value = await aiApi.hotwords(hotCourseId.value);
  } catch {
    hotwords.value = [];
  } finally {
    hotLoading.value = false;
  }
}

function hotFont(count: number): number {
  // 11 ~ 18 px,频次越高字越大
  return Math.min(18, 11 + count);
}

// ====== 3. 班级错误分析 ======
const errCourseId = ref('');
const errHwId = ref<number | null>(null);
const homeworks = ref<Homework[]>([]);
const hwLoading = ref(false);
const errLoading = ref(false);
const errReport = ref<AiErrorReport | null>(null);

async function loadHomeworks() {
  errHwId.value = null;
  errReport.value = null;
  hwLoading.value = true;
  try {
    homeworks.value = await homeworkApi.list(errCourseId.value || undefined);
  } catch {
    homeworks.value = [];
  } finally {
    hwLoading.value = false;
  }
}

async function onAnalyze() {
  if (!errHwId.value) return;
  errLoading.value = true;
  errReport.value = null;
  try {
    errReport.value = await aiApi.analyzeErrors(errHwId.value);
  } catch {
    /* http.ts 已 toast */
  } finally {
    errLoading.value = false;
  }
}

// ====== 4. 知识库 CRUD ======
const kbCourseId = ref('');
const knowledge = ref<AiKnowledge[]>([]);
const kbLoading = ref(false);
const kbDialog = ref(false);
const kbSaving = ref(false);
const kbDeleting = ref<number | null>(null);
const kbForm = ref<AiKnowledgePayload & { id?: number }>({
  course_id: '',
  title: '',
  content: '',
  subject: '',
  difficulty: 1,
  sort_order: 0,
  status: 1,
});

async function loadKnowledge() {
  kbLoading.value = true;
  try {
    knowledge.value = await aiApi.listKnowledge(kbCourseId.value || undefined);
  } catch {
    knowledge.value = [];
  } finally {
    kbLoading.value = false;
  }
}

function openKbDialog(row?: AiKnowledge) {
  if (row) {
    kbForm.value = {
      id: row.id,
      course_id: row.course_id || '',
      title: row.title,
      content: row.content,
      subject: row.subject || '',
      difficulty: row.difficulty,
      sort_order: row.sort_order,
      status: row.status,
    };
  } else {
    resetKbForm();
  }
  kbDialog.value = true;
}

function resetKbForm() {
  kbForm.value = {
    course_id: kbCourseId.value || '',
    title: '',
    content: '',
    subject: '',
    difficulty: 1,
    sort_order: 0,
    status: 1,
  };
}

async function onSaveKnowledge() {
  if (!kbForm.value.title.trim()) {
    ElMessage.warning('请填写标题');
    return;
  }
  if (!kbForm.value.course_id) {
    ElMessage.warning('请选择课程');
    return;
  }
  kbSaving.value = true;
  try {
    if (kbForm.value.id) {
      await aiApi.updateKnowledge({
        ...(kbForm.value as AiKnowledgePayload & { id: number }),
      });
    } else {
      await aiApi.createKnowledge(kbForm.value);
    }
    ElMessage.success('已保存');
    kbDialog.value = false;
    await loadKnowledge();
  } catch {
    /* http.ts 已 toast */
  } finally {
    kbSaving.value = false;
  }
}

async function onDeleteKnowledge(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该知识点?', '提示', { type: 'warning' });
  } catch {
    return;
  }
  kbDeleting.value = id;
  try {
    await aiApi.deleteKnowledge(id);
    ElMessage.success('已删除');
    await loadKnowledge();
  } catch {
    /* http.ts 已 toast */
  } finally {
    kbDeleting.value = null;
  }
}

// ====== 5. 评分规则 CRUD ======
const ruleCourseId = ref('');
const rules = ref<AiRule[]>([]);
const ruleLoading = ref(false);
const ruleDialog = ref(false);
const ruleSaving = ref(false);
const ruleDeleting = ref<number | null>(null);
const ruleForm = ref<AiRulePayload & { id?: number }>({
  course_id: '',
  name: '',
  content: '',
  rule_type: 'score_point',
  weight: 0,
  max_score: 0,
  criteria: '',
  sort_order: 0,
  status: 1,
});

async function loadRules() {
  ruleLoading.value = true;
  try {
    rules.value = await aiApi.listRules(ruleCourseId.value || undefined);
  } catch {
    rules.value = [];
  } finally {
    ruleLoading.value = false;
  }
}

function openRuleDialog(row?: AiRule) {
  if (row) {
    ruleForm.value = {
      id: row.id,
      course_id: row.course_id || '',
      name: row.name,
      content: row.content,
      subject: row.subject || '',
      rule_type: row.rule_type,
      weight: row.weight,
      max_score: row.max_score,
      criteria: row.criteria || '',
      sort_order: row.sort_order,
      status: row.status,
    };
  } else {
    resetRuleForm();
  }
  ruleDialog.value = true;
}

function resetRuleForm() {
  ruleForm.value = {
    course_id: ruleCourseId.value || '',
    name: '',
    content: '',
    rule_type: 'score_point',
    weight: 0,
    max_score: 0,
    criteria: '',
    sort_order: 0,
    status: 1,
  };
}

async function onSaveRule() {
  if (!ruleForm.value.name.trim()) {
    ElMessage.warning('请填写规则名称');
    return;
  }
  ruleSaving.value = true;
  try {
    if (ruleForm.value.id) {
      await aiApi.updateRule({
        ...(ruleForm.value as AiRulePayload & { id: number }),
      });
    } else {
      await aiApi.createRule(ruleForm.value);
    }
    ElMessage.success('已保存');
    ruleDialog.value = false;
    await loadRules();
  } catch {
    /* http.ts 已 toast */
  } finally {
    ruleSaving.value = false;
  }
}

async function onDeleteRule(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该评分规则?', '提示', { type: 'warning' });
  } catch {
    return;
  }
  ruleDeleting.value = id;
  try {
    await aiApi.deleteRule(id);
    ElMessage.success('已删除');
    await loadRules();
  } catch {
    /* http.ts 已 toast */
  } finally {
    ruleDeleting.value = null;
  }
}

// ====== 初始化 ======
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

onMounted(async () => {
  await loadCourses();
  // 默认选中第一个课程
  if (courses.value.length) {
    assistCourseId.value = courses.value[0].course_id;
    hotCourseId.value = courses.value[0].course_id;
    kbCourseId.value = courses.value[0].course_id;
    ruleCourseId.value = courses.value[0].course_id;
  }
  loadKnowledge();
  loadRules();
  loadHomeworks();
});
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.card-title {
  font-weight: 600;
}
.light {
  color: var(--text-sub);
  font-size: 12.5px;
}
.row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 12px;
}
.out {
  background: #f8fafd;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Consolas', 'Menlo', monospace;
  margin: 0;
  min-height: 80px;
}
.hotwords {
  margin-top: 8px;
  line-height: 2;
}
.hot-badge {
  display: inline-block;
  margin: 4px 6px;
  padding: 4px 12px;
  border-radius: 14px;
  background: var(--amber-soft, #fef3c7);
  color: #92400e;
  font-weight: 600;
  em {
    font-style: normal;
    font-size: 11px;
    margin-left: 4px;
    opacity: 0.7;
  }
}
.err-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.ai-tabs {
  :deep(.el-tabs__content) {
    padding-top: 4px;
  }
}
</style>
