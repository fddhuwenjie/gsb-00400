<template>
  <div>
    <div class="page-header">
      <h1>版本管理</h1>
      <p class="subtitle">按文档标识管理版本，审核通过后发布到搜索与统计</p>
    </div>

    <div v-if="loading" class="loading-card">
      <div class="spinner"></div>
      <p>加载文档列表中...</p>
    </div>

    <template v-else>
      <!-- 文档分组列表 -->
      <div v-if="groups.length" class="group-list">
        <div
          v-for="g in groups" :key="g.doc_key"
          :class="['group-card', { active: g.doc_key === selectedKey }]"
          @click="selectGroup(g.doc_key)"
        >
          <div class="group-title">{{ g.title }}</div>
          <div class="group-key">{{ g.doc_key }}</div>
          <div class="group-meta">
            <span class="tag">{{ g.bucket || '未分类' }}</span>
            <span class="ver-count">共 {{ g.version_count }} 版</span>
            <span v-if="g.published_version_no" class="published-badge">已发布 v{{ g.published_version_no }}</span>
            <span v-else class="status pending">未发布</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-card"><p>暂无文档，请先在文件管理中上传</p></div>

      <!-- 版本列表 -->
      <div v-if="selectedKey" class="card versions-card">
        <h3>版本历史 <span class="doc-key-label">{{ selectedKey }}</span></h3>
        <table v-if="versions.length" class="desktop-table">
          <thead>
            <tr><th>版本</th><th>文件名</th><th>上传人</th><th>上传时间</th><th>变更说明</th><th>审核状态</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="v in versions" :key="v.id" :class="{ 'row-active': detail && detail.id === v.id }">
              <td>
                <span class="ver-no">v{{ v.version_no }}</span>
                <span v-if="v.is_published" class="published-badge">当前发布</span>
              </td>
              <td class="filename-cell">{{ v.filename }}</td>
              <td>{{ v.uploaded_by || '-' }}</td>
              <td>{{ formatTime(v.uploaded_at) }}</td>
              <td class="note-cell">{{ v.change_note || '-' }}</td>
              <td>
                <span :class="['status', v.review_status]">{{ reviewMap[v.review_status] }}</span>
                <div v-if="v.review_note" class="review-note">退回：{{ v.review_note }}</div>
              </td>
              <td class="actions-cell">
                <button class="btn-view" @click="toggleDetail(v.id)">详情</button>
                <button v-if="v.review_status !== 'approved'" class="btn-approve" @click="review(v, 'approve')">通过</button>
                <button v-if="v.review_status !== 'rejected'" class="btn-reject" @click="startReject(v)">退回</button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 移动端版本卡片 -->
        <div v-if="versions.length" class="mobile-cards">
          <div v-for="v in versions" :key="'m'+v.id" class="version-card">
            <div class="version-card-head">
              <span class="ver-no">v{{ v.version_no }}</span>
              <span v-if="v.is_published" class="published-badge">当前发布</span>
              <span :class="['status', v.review_status]">{{ reviewMap[v.review_status] }}</span>
            </div>
            <div class="version-card-name">{{ v.filename }}</div>
            <div class="version-card-meta">{{ v.uploaded_by || '-' }} · {{ formatTime(v.uploaded_at) }}</div>
            <div v-if="v.change_note" class="version-card-note">{{ v.change_note }}</div>
            <div v-if="v.review_note" class="review-note">退回：{{ v.review_note }}</div>
            <div class="version-card-actions">
              <button class="btn-view" @click="toggleDetail(v.id)">详情</button>
              <button v-if="v.review_status !== 'approved'" class="btn-approve" @click="review(v, 'approve')">通过</button>
              <button v-if="v.review_status !== 'rejected'" class="btn-reject" @click="startReject(v)">退回</button>
            </div>
          </div>
        </div>
        <div v-if="!versions.length" class="empty">该文档暂无版本</div>

        <!-- 退回原因输入 -->
        <div v-if="rejectTarget" class="reject-bar">
          <span>退回 v{{ rejectTarget.version_no }}：</span>
          <input v-model="rejectNote" type="text" placeholder="请输入退回原因（可选）" @keyup.enter="confirmReject" />
          <button class="btn-reject-confirm" @click="confirmReject">确认退回</button>
          <button class="btn-cancel" @click="rejectTarget = null">取消</button>
        </div>
      </div>

      <!-- 版本详情 -->
      <div v-if="detail" class="card detail-card">
        <h3>版本详情 <span class="ver-no">v{{ detail.version_no }}</span>
          <span v-if="detail.is_published" class="published-badge">当前发布</span>
          <span :class="['status', detail.review_status]">{{ reviewMap[detail.review_status] }}</span>
        </h3>
        <div class="detail-grid">
          <div><label>文件名</label><p>{{ detail.filename }}</p></div>
          <div><label>标准名</label><p>{{ detail.standard_name || '未生成' }}</p></div>
          <div><label>分类</label><p>{{ detail.bucket || '-' }}</p></div>
          <div><label>上传人 / 时间</label><p>{{ detail.uploaded_by || '-' }} · {{ formatTime(detail.uploaded_at) }}</p></div>
          <div class="span-2"><label>变更说明</label><p>{{ detail.change_note || '-' }}</p></div>
          <div class="span-2"><label>摘要</label><p class="summary">{{ detail.summary || '暂无摘要' }}</p></div>
        </div>
        <div v-if="detail.tags && detail.tags.length" class="tags">
          <span v-for="(t, i) in detail.tags" :key="i" class="tag">{{ t.tag_name }}: {{ t.tag_value }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { docs } from '../api'
import { useToast } from '../composables/useToast'

const toast = useToast()
const groups = ref([])
const versions = ref([])
const detail = ref(null)
const selectedKey = ref('')
const loading = ref(true)
const rejectTarget = ref(null)
const rejectNote = ref('')

const reviewMap = { pending: '待审核', approved: '已通过', rejected: '已退回' }

const formatTime = (t) => t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'

const loadGroups = async () => {
  loading.value = true
  try {
    const { data } = await docs.groups()
    groups.value = data.groups || []
    if (groups.value.length && !selectedKey.value) {
      await selectGroup(groups.value[0].doc_key)
    }
  } catch { toast.error('加载文档列表失败') }
  finally { loading.value = false }
}

const selectGroup = async (docKey) => {
  selectedKey.value = docKey
  detail.value = null
  rejectTarget.value = null
  await loadVersions()
}

const loadVersions = async () => {
  try {
    const { data } = await docs.versions(selectedKey.value)
    versions.value = data.versions || []
    if (detail.value) {
      const cur = versions.value.find(v => v.id === detail.value.id)
      if (cur) await toggleDetail(cur.id, true)
    }
  } catch { toast.error('加载版本列表失败') }
}

const toggleDetail = async (versionId, force = false) => {
  if (detail.value && detail.value.id === versionId && !force) {
    detail.value = null
    return
  }
  try {
    const { data } = await docs.versionDetail(versionId)
    detail.value = data
  } catch { toast.error('加载版本详情失败') }
}

const review = async (v, action, note = '') => {
  try {
    await docs.reviewVersion(v.id, action, note)
    toast.success(action === 'approve' ? `v${v.version_no} 已通过审核` : `v${v.version_no} 已退回`)
    await loadGroups()
    await loadVersions()
  } catch { toast.error('审核操作失败') }
}

const startReject = (v) => {
  rejectTarget.value = v
  rejectNote.value = ''
}

const confirmReject = async () => {
  const v = rejectTarget.value
  rejectTarget.value = null
  await review(v, 'reject', rejectNote.value.trim())
}

onMounted(loadGroups)
</script>

<style scoped>
.page-header { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 24px; }
h1 { font-size: 24px; color: #1e293b; }
.subtitle { color: #64748b; }
.group-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-bottom: 24px; }
.group-card { background: white; padding: 16px; border-radius: 12px; border: 1px solid #e2e8f0; cursor: pointer; transition: border-color 0.2s; }
.group-card:hover { border-color: #c7d2fe; }
.group-card.active { border-color: #6366f1; box-shadow: 0 0 0 1px #6366f1; }
.group-title { font-weight: 600; color: #1e293b; margin-bottom: 4px; word-break: break-all; }
.group-key { font-size: 12px; color: #94a3b8; margin-bottom: 8px; word-break: break-all; }
.group-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.ver-count { font-size: 12px; color: #64748b; }
.card { background: white; border-radius: 12px; border: 1px solid #e2e8f0; padding: 24px; margin-bottom: 24px; overflow-x: auto; }
.card h3 { font-size: 16px; color: #1e293b; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; }
.doc-key-label { font-size: 13px; color: #94a3b8; font-weight: 400; margin-left: 8px; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 12px 14px; font-size: 12px; color: #64748b; border-bottom: 1px solid #e2e8f0; text-transform: uppercase; white-space: nowrap; }
td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; font-size: 14px; vertical-align: top; }
tr.row-active { background: #f8faff; }
.filename-cell { max-width: 220px; word-break: break-all; }
.note-cell { max-width: 180px; word-break: break-all; color: #64748b; }
.ver-no { display: inline-block; padding: 2px 8px; background: #e0e7ff; color: #4338ca; border-radius: 10px; font-size: 12px; font-weight: 600; margin-right: 6px; }
.published-badge { display: inline-block; padding: 2px 8px; background: #dcfce7; color: #166534; border-radius: 10px; font-size: 12px; font-weight: 600; }
.status { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status.pending { background: #f1f5f9; color: #64748b; }
.status.approved { background: #dcfce7; color: #166534; }
.status.rejected { background: #fee2e2; color: #991b1b; }
.review-note { font-size: 12px; color: #991b1b; margin-top: 4px; }
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.actions-cell { white-space: nowrap; }
.actions-cell button, .version-card-actions button { margin-right: 8px; padding: 6px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn-view { background: #f1f5f9; color: #475569; }
.btn-approve { background: #10b981; color: white; }
.btn-reject { background: #fee2e2; color: #991b1b; }
.reject-bar { display: flex; align-items: center; gap: 10px; margin-top: 16px; padding: 14px; background: #fef2f2; border-radius: 8px; flex-wrap: wrap; }
.reject-bar span { font-size: 14px; color: #991b1b; }
.reject-bar input { flex: 1; min-width: 200px; padding: 8px 12px; border: 1px solid #fecaca; border-radius: 6px; font-size: 14px; }
.btn-reject-confirm { padding: 8px 16px; background: #dc2626; color: white; border: none; border-radius: 6px; cursor: pointer; }
.btn-cancel { padding: 8px 16px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; color: #64748b; }
.detail-card label { font-size: 12px; color: #64748b; text-transform: uppercase; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.detail-grid p { margin-top: 4px; color: #1e293b; font-size: 14px; word-break: break-all; }
.span-2 { grid-column: span 2; }
.summary { background: #f8fafc; padding: 12px; border-radius: 8px; color: #475569; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; }
.empty { padding: 40px; text-align: center; color: #94a3b8; }
.empty-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; border: 1px solid #e2e8f0; }
.loading-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; border: 1px solid #e2e8f0; }
.loading-card p { margin-top: 16px; font-size: 15px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.mobile-cards { display: none; }
@media (max-width: 768px) {
  .desktop-table { display: none; }
  .mobile-cards { display: block; }
  .version-card { padding: 16px; border-bottom: 1px solid #f1f5f9; }
  .version-card-head { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
  .version-card-name { font-weight: 600; color: #1e293b; word-break: break-all; }
  .version-card-meta { font-size: 12px; color: #94a3b8; margin: 4px 0; }
  .version-card-note { font-size: 13px; color: #64748b; margin-bottom: 8px; }
  .version-card-actions { margin-top: 8px; }
  .detail-grid { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1; }
}
</style>
