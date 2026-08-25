<template>
  <div>
    <div class="page-header">
      <div>
        <button class="back-link" @click="$router.push('/files')">← 返回文件管理</button>
        <h1>{{ doc.title || doc.doc_key }}</h1>
        <p>
          业务标识：{{ doc.doc_key }}
          <span class="tag">{{ doc.bucket || '未分类' }}</span>
          共 {{ versions.length }} 个版本
          <template v-if="doc.published_version">
            · 当前发布
            <span class="version-badge published">v{{ doc.published_version }}</span>
          </template>
          <template v-else>· <span class="muted">尚无发布版本</span></template>
        </p>
      </div>
    </div>

    <div v-if="loading" class="loading-card">
      <div class="spinner"></div>
      <p>加载版本信息中...</p>
    </div>

    <div v-else class="detail-layout">
      <!-- 版本列表 -->
      <div class="card version-list">
        <div class="card-title">版本历史</div>
        <div
          v-for="v in versions"
          :key="v.file_id"
          :class="['version-item', { active: selectedId === v.file_id }]"
          @click="selectVersion(v.file_id)"
        >
          <div class="version-item-head">
            <span class="version-badge" :class="{ published: v.is_published }">v{{ v.version_number }}</span>
            <span v-if="v.is_published" :class="['status', 'approved']">已发布</span>
            <span v-else-if="v.review_status === 'pending'" :class="['status', 'pending']">待审核</span>
            <span v-else-if="v.review_status === 'rejected'" :class="['status', 'rejected']">已退回</span>
            <span v-else-if="v.review_status === 'approved'" :class="['status', 'approved']">已通过</span>
          </div>
          <div class="version-meta">
            {{ v.uploaded_by || '未知用户' }} · {{ formatDate(v.upload_date) }}
          </div>
          <div v-if="v.change_note" class="version-note">📝 {{ v.change_note }}</div>
          <div v-if="v.review_status === 'rejected' && v.review_comment" class="review-comment-reject">
            退回原因：{{ v.review_comment }}
          </div>
        </div>
      </div>

      <!-- 版本详情 -->
      <div class="card version-detail">
        <template v-if="current">
          <div class="detail-title-row">
            <div>
              <span class="version-badge" :class="{ published: current.is_published }">版本 v{{ current.version_number }}</span>
              <span :class="['status', reviewStatusClass(current.review_status)]">
                {{ reviewStatusText(current.review_status) }}
              </span>
            </div>
            <div v-if="current.status !== 'completed'" class="muted">
              文件{{ statusText[current.status] || '处理中' }}，完成后才能审核
            </div>
          </div>

          <div class="detail-grid">
            <div class="detail-item"><label>文件名</label><div>{{ current.name }}</div></div>
            <div class="detail-item"><label>AI标准名</label><div>{{ current.standard_name || '未生成' }}</div></div>
            <div class="detail-item"><label>分类</label><div>{{ current.bucket || '-' }}</div></div>
            <div class="detail-item"><label>上传人</label><div>{{ current.uploaded_by || '未知' }}</div></div>
            <div class="detail-item"><label>上传时间</label><div>{{ formatDate(current.upload_date) }}</div></div>
            <div class="detail-item"><label>变更说明</label><div>{{ current.change_note || '（未填写）' }}</div></div>
          </div>

          <div v-if="tags.length" class="detail-tags">
            <label>标签</label>
            <div class="tag-list">
              <span v-for="t in tags" :key="t.id" class="tag">{{ t.tag_name }}: {{ t.tag_value }}</span>
            </div>
          </div>

          <div v-if="current.summary" class="detail-summary">
            <label>内容摘要</label>
            <div class="summary-text">{{ current.summary }}</div>
          </div>

          <div v-if="current.review_comment" class="detail-comment">
            <label>审核意见</label>
            <div class="comment-text">{{ current.review_comment }}</div>
          </div>

          <!-- 审核操作区 -->
          <div v-if="current.review_status === 'pending' && current.status === 'completed'" class="review-box">
            <label class="review-label">审核意见（退回时必填原因）</label>
            <textarea v-model="reviewComment" class="review-input" rows="2" placeholder="填写审核意见或退回原因..."></textarea>
            <div class="review-actions">
              <button class="btn-approve" :disabled="submitting" @click="doReview('approve')">✓ 通过并发布</button>
              <button class="btn-reject" :disabled="submitting" @click="doReview('reject')">✗ 退回</button>
            </div>
            <p class="review-hint">通过后该版本成为当前发布版本并进入搜索与统计，同文档旧发布版本自动下线；退回版本不会被检索。</p>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { documents, files } from '../api'
import { useToast } from '../composables/useToast'

const route = useRoute()
const toast = useToast()
const doc = ref({})
const versions = ref([])
const selectedId = ref(null)
const current = ref(null)
const tags = ref([])
const loading = ref(true)
const submitting = ref(false)
const reviewComment = ref('')

const statusText = { pending: '排队中', processing: '处理中', completed: '已完成', failed: '处理失败' }

const formatDate = (s) => {
  if (!s) return '-'
  const d = new Date(s)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const reviewStatusText = (s) => ({ pending: '待审核', approved: '审核通过', rejected: '已退回' }[s] || s)
const reviewStatusClass = (s) => ({ pending: 'pending', approved: 'approved', rejected: 'rejected' }[s] || 'pending')

const load = async () => {
  loading.value = true
  try {
    const { data } = await documents.get(route.params.id)
    doc.value = data.document
    versions.value = data.versions || []
    if (!versions.value.length) {
      current.value = null
      return
    }
    const target = versions.value.find(v => v.is_published)
      || versions.value.find(v => v.review_status === 'pending')
      || versions.value[0]
    await selectVersion(target.file_id)
  } catch {
    toast.error('加载文档详情失败')
  } finally {
    loading.value = false
  }
}

const selectVersion = async (fileId) => {
  selectedId.value = fileId
  reviewComment.value = ''
  try {
    const { data } = await files.get(fileId)
    current.value = data.file
    tags.value = data.tags || []
  } catch {
    toast.error('加载版本详情失败')
  }
}

const doReview = async (action) => {
  if (action === 'reject' && !reviewComment.value.trim()) {
    toast.error('退回时请填写退回原因')
    return
  }
  submitting.value = true
  try {
    await files.review(current.value.file_id, action, reviewComment.value.trim() || null)
    toast.success(action === 'approve' ? '已通过并发布该版本' : '已退回该版本')
    await load()
  } catch (err) {
    toast.error(err?.response?.data?.detail || err?.response?.data?.message || '审核操作失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 24px; }
.back-link { background: none; border: none; color: #6366f1; cursor: pointer; font-size: 14px; padding: 0 0 8px 0; }
h1 { font-size: 22px; color: #1e293b; }
p { color: #64748b; font-size: 14px; margin-top: 6px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.version-badge { background: #f1f5f9; color: #475569; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.version-badge.published { background: #dcfce7; color: #166534; }
.muted { color: #94a3b8; font-size: 13px; }
.status { padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status.pending { background: #f1f5f9; color: #64748b; }
.status.approved { background: #dcfce7; color: #166534; }
.status.rejected { background: #fee2e2; color: #991b1b; }
.loading-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; border: 1px solid #e2e8f0; }
.loading-card p { margin-top: 16px; font-size: 15px; justify-content: center; }
.spinner { width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.detail-layout { display: grid; grid-template-columns: 320px 1fr; gap: 20px; align-items: start; }
.card { background: white; border-radius: 12px; border: 1px solid #e2e8f0; padding: 20px; }
.card-title { font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 12px; }
.version-item { padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 10px; cursor: pointer; transition: all 0.15s; }
.version-item:hover { border-color: #c7d2fe; }
.version-item.active { border-color: #6366f1; background: #eef2ff; }
.version-item-head { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
.version-meta { font-size: 12px; color: #64748b; }
.version-note { font-size: 13px; color: #334155; margin-top: 6px; background: #f8fafc; padding: 6px 8px; border-radius: 6px; word-break: break-all; }
.review-comment-reject { font-size: 12px; color: #991b1b; margin-top: 6px; background: #fef2f2; padding: 6px 8px; border-radius: 6px; word-break: break-all; }
.detail-title-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 8px; }
.detail-title-row > div:first-child { display: flex; gap: 8px; align-items: center; }
.detail-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.detail-item label { font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px; }
.detail-item div { font-size: 14px; color: #1e293b; word-break: break-all; }
.detail-tags, .detail-summary, .detail-comment { margin-top: 20px; }
.detail-tags label, .detail-summary label, .detail-comment label, .review-label { font-size: 12px; color: #94a3b8; display: block; margin-bottom: 8px; }
.tag-list { display: flex; gap: 8px; flex-wrap: wrap; }
.summary-text, .comment-text { padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 14px; color: #334155; white-space: pre-wrap; word-break: break-all; max-height: 260px; overflow-y: auto; }
.comment-text { background: #fefce8; }
.review-box { margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 20px; }
.review-input { width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; font-size: 14px; resize: vertical; font-family: inherit; box-sizing: border-box; }
.review-input:focus { outline: none; border-color: #6366f1; }
.review-actions { display: flex; gap: 12px; margin-top: 12px; }
.btn-approve { padding: 10px 20px; background: #10b981; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-approve:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-reject { padding: 10px 20px; background: white; color: #dc2626; border: 1px solid #fecaca; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-reject:disabled { opacity: 0.6; cursor: not-allowed; }
.review-hint { font-size: 12px; color: #94a3b8; margin-top: 10px; line-height: 1.6; }
@media (max-width: 768px) {
  .detail-layout { grid-template-columns: 1fr; }
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
