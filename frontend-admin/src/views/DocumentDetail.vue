<template>
  <div>
    <div class="page-header">
      <div>
        <button class="btn-back" @click="$router.push('/files')">← 返回文件管理</button>
        <h1>{{ doc?.title || '文档详情' }}</h1>
        <p class="subtitle">文档标识：{{ doc?.document_key }}</p>
      </div>
    </div>

    <div v-if="loading" class="loading-card">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="doc" class="detail-layout">
      <div class="version-sidebar card">
        <h3>版本历史</h3>
        <div class="version-list">
          <div
            v-for="v in doc.versions"
            :key="v.id"
            :class="['version-item', { active: selectedVersion?.id === v.id }]"
            @click="selectVersion(v)"
          >
            <div class="version-top">
              <span :class="['version-badge', v.is_current ? 'current' : (v.review_status === 'approved' ? 'approved-old' : 'old')]">
                v{{ v.version_number }}
              </span>
              <span v-if="v.is_current" class="current-tag">当前版本</span>
            </div>
            <div class="version-name">{{ v.original_name }}</div>
            <div class="version-meta">
              <span :class="['status', v.review_status]">{{ reviewMap[v.review_status] }}</span>
            </div>
            <div v-if="v.change_description" class="version-change">
              {{ v.change_description }}
            </div>
            <div class="version-info">
              <span v-if="v.uploader_name">上传：{{ v.uploader_name }}</span>
              <span v-if="v.uploaded_at">{{ formatDate(v.uploaded_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="version-detail card" v-if="selectedVersion">
        <div class="detail-header">
          <div>
            <h2>
              <span :class="['version-badge large', selectedVersion.is_current ? 'current' : 'old']">
                v{{ selectedVersion.version_number }}
              </span>
              {{ selectedVersion.original_name }}
            </h2>
            <p class="detail-sub">{{ selectedVersion.standard_name || '未生成标准名' }}</p>
          </div>
          <div class="detail-actions">
            <button
              v-if="selectedVersion.review_status === 'approved' && !selectedVersion.is_current"
              class="btn-switch"
              @click="switchVersion"
            >
              🔄 切换为当前版本
            </button>
            <button
              v-if="selectedVersion.process_status === 'completed' && selectedVersion.review_status === 'pending'"
              class="btn-approve"
              @click="openReview('approve')"
            >
              ✓ 通过
            </button>
            <button
              v-if="selectedVersion.process_status === 'completed' && selectedVersion.review_status === 'pending'"
              class="btn-reject"
              @click="openReview('reject')"
            >
              ✗ 退回
            </button>
          </div>
        </div>

        <div class="info-grid">
          <div class="info-item">
            <label>处理状态</label>
            <span :class="['status', selectedVersion.process_status]">{{ statusMap[selectedVersion.process_status] }}</span>
          </div>
          <div class="info-item">
            <label>审核状态</label>
            <span :class="['status', selectedVersion.review_status]">{{ reviewMap[selectedVersion.review_status] }}</span>
          </div>
          <div class="info-item">
            <label>分类</label>
            <span class="tag">{{ selectedVersion.bucket }}</span>
          </div>
          <div class="info-item" v-if="selectedVersion.uploader_name">
            <label>上传人</label>
            <span>{{ selectedVersion.uploader_name }}</span>
          </div>
          <div class="info-item" v-if="selectedVersion.reviewer_name">
            <label>审核人</label>
            <span>{{ selectedVersion.reviewer_name }}</span>
          </div>
          <div class="info-item" v-if="selectedVersion.uploaded_at">
            <label>上传时间</label>
            <span>{{ formatDate(selectedVersion.uploaded_at) }}</span>
          </div>
          <div class="info-item" v-if="selectedVersion.reviewed_at">
            <label>审核时间</label>
            <span>{{ formatDate(selectedVersion.reviewed_at) }}</span>
          </div>
        </div>

        <div v-if="selectedVersion.change_description" class="info-block">
          <label>变更说明</label>
          <div class="info-content">{{ selectedVersion.change_description }}</div>
        </div>

        <div v-if="selectedVersion.review_comment" class="info-block">
          <label>审核意见</label>
          <div class="info-content review-comment">{{ selectedVersion.review_comment }}</div>
        </div>

        <div v-if="versionDetail" class="info-block">
          <label>文档摘要</label>
          <div class="info-content">{{ versionDetail.file?.summary || '暂无摘要' }}</div>
        </div>

        <div v-if="versionDetail?.tags?.length" class="info-block">
          <label>标签</label>
          <div class="tags-row">
            <span v-for="t in versionDetail.tags" :key="t.id" class="tag">{{ t.value }}</span>
          </div>
        </div>

        <div v-if="versionDetail?.chunks?.length" class="info-block">
          <label>文本片段（{{ versionDetail.chunks.length }}）</label>
          <div class="chunks-list">
            <div v-for="(c, i) in displayedChunks" :key="i" class="chunk-item">
              <span class="chunk-index">#{{ c.index + 1 }}</span>
              {{ c.content }}
            </div>
            <button v-if="versionDetail.chunks.length > 5" class="btn-more" @click="showAllChunks = !showAllChunks">
              {{ showAllChunks ? '收起' : `展开全部 ${versionDetail.chunks.length} 段` }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showReviewModal" class="modal-overlay" @click.self="showReviewModal = false">
      <div class="modal">
        <h3>{{ reviewAction === 'approve' ? '通过审核' : '退回版本' }}</h3>
        <p class="modal-desc">
          版本 v{{ selectedVersion?.version_number }} - {{ selectedVersion?.original_name }}
        </p>
        <textarea
          v-model="reviewComment"
          :placeholder="reviewAction === 'approve' ? '审核意见（可选）' : '请输入退回原因...'"
          rows="4"
        ></textarea>
        <div class="modal-actions">
          <button class="btn-cancel-modal" @click="showReviewModal = false">取消</button>
          <button
            :class="reviewAction === 'approve' ? 'btn-approve' : 'btn-reject'"
            @click="submitReview"
          >
            确认{{ reviewAction === 'approve' ? '通过' : '退回' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { documents } from '../api'
import { useToast } from '../composables/useToast'

const route = useRoute()
const toast = useToast()
const doc = ref(null)
const loading = ref(true)
const selectedVersionId = ref(null)
const versionDetail = ref(null)
const showAllChunks = ref(false)
const showReviewModal = ref(false)
const reviewAction = ref('approve')
const reviewComment = ref('')

const statusMap = { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }
const reviewMap = { pending: '待审核', approved: '已通过', rejected: '已退回' }

const selectedVersion = computed(() => {
  if (!doc.value) return null
  return doc.value.versions.find(v => v.id === selectedVersionId.value) || doc.value.versions[0]
})

const displayedChunks = computed(() => {
  if (!versionDetail.value?.chunks) return []
  return showAllChunks.value ? versionDetail.value.chunks : versionDetail.value.chunks.slice(0, 5)
})

const load = async () => {
  loading.value = true
  try {
    const id = route.params.id
    const { data } = await documents.get(id)
    doc.value = data
    const current = data.versions.find(v => v.is_current)
    selectedVersionId.value = current ? current.id : (data.versions[0]?.id || null)
  } catch {
    toast.error('加载文档详情失败')
  } finally {
    loading.value = false
  }
}

const selectVersion = async (v) => {
  selectedVersionId.value = v.id
  versionDetail.value = null
  showAllChunks.value = false
  try {
    const { data } = await documents.getVersion(doc.value.id, v.id)
    versionDetail.value = data
  } catch {
    toast.error('加载版本详情失败')
  }
}

const switchVersion = async () => {
  if (!selectedVersion.value) return
  try {
    await documents.switchVersion(doc.value.id, selectedVersion.value.id)
    toast.success(`已切换到 v${selectedVersion.value.version_number}`)
    await load()
  } catch {
    toast.error('切换版本失败')
  }
}

const openReview = (action) => {
  reviewAction.value = action
  reviewComment.value = ''
  showReviewModal.value = true
}

const submitReview = async () => {
  if (!selectedVersion.value) return
  try {
    await documents.reviewVersion(
      doc.value.id,
      selectedVersion.value.id,
      reviewAction.value,
      reviewComment.value || null
    )
    toast.success(reviewAction.value === 'approve' ? '已通过审核，该版本已设为当前版本' : '已退回该版本')
    showReviewModal.value = false
    await load()
  } catch {
    toast.error('审核操作失败')
  }
}

const formatDate = (d) => {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

watch(() => route.params.id, load)
onMounted(load)
</script>

<style scoped>
.page-header { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 24px; }
.btn-back { background: none; border: none; color: #6366f1; cursor: pointer; font-size: 14px; padding: 0; margin-bottom: 8px; }
h1 { font-size: 24px; color: #1e293b; }
.subtitle { color: #64748b; font-size: 13px; margin-top: 4px; }
.loading-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; border: 1px solid #e2e8f0; }
.spinner { width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.detail-layout { display: grid; grid-template-columns: 320px 1fr; gap: 24px; }
.card { background: white; border-radius: 12px; border: 1px solid #e2e8f0; padding: 24px; }
.version-sidebar h3, .version-detail h3 { font-size: 16px; color: #1e293b; margin-bottom: 16px; }
.version-list { display: flex; flex-direction: column; gap: 8px; max-height: 70vh; overflow-y: auto; }
.version-item { padding: 12px; border: 1px solid #f1f5f9; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
.version-item:hover { border-color: #c7d2fe; background: #f8fafc; }
.version-item.active { border-color: #6366f1; background: #eef2ff; }
.version-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.version-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.version-badge.large { font-size: 14px; padding: 4px 12px; margin-right: 8px; }
.version-badge.current { background: #dbeafe; color: #1e40af; }
.version-badge.approved-old { background: #dcfce7; color: #166534; }
.version-badge.old { background: #f1f5f9; color: #64748b; }
.current-tag { font-size: 11px; color: #2563eb; font-weight: 500; }
.version-name { font-size: 13px; color: #1e293b; margin-bottom: 6px; word-break: break-all; }
.version-meta { margin-bottom: 6px; }
.version-change { font-size: 12px; color: #475569; background: #f8fafc; padding: 6px 8px; border-radius: 6px; margin-bottom: 6px; }
.version-info { font-size: 11px; color: #94a3b8; display: flex; flex-direction: column; gap: 2px; }
.status { padding: 2px 8px; border-radius: 10px; font-size: 11px; }
.status.pending { background: #f1f5f9; color: #64748b; }
.status.processing { background: #fef3c7; color: #92400e; }
.status.completed, .status.approved { background: #dcfce7; color: #166534; }
.status.failed, .status.rejected { background: #fee2e2; color: #991b1b; }
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #f1f5f9; }
.detail-header h2 { font-size: 18px; color: #1e293b; display: flex; align-items: center; }
.detail-sub { color: #64748b; font-size: 14px; margin-top: 6px; }
.detail-actions { display: flex; gap: 8px; }
.btn-approve, .btn-reject, .btn-switch { padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; white-space: nowrap; }
.btn-approve { background: #10b981; color: white; }
.btn-reject { background: #f1f5f9; color: #64748b; }
.btn-switch { background: #6366f1; color: white; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px; }
.info-item { display: flex; flex-direction: column; gap: 4px; }
.info-item label { font-size: 11px; color: #94a3b8; text-transform: uppercase; }
.info-block { margin-bottom: 20px; }
.info-block label { font-size: 12px; color: #64748b; text-transform: uppercase; display: block; margin-bottom: 8px; }
.info-content { padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 14px; color: #334155; line-height: 1.6; }
.review-comment { background: #fef2f2; color: #991b1b; }
.tags-row { display: flex; flex-wrap: wrap; gap: 8px; }
.chunks-list { display: flex; flex-direction: column; gap: 8px; }
.chunk-item { padding: 10px 12px; background: #f8fafc; border-radius: 8px; font-size: 13px; color: #475569; line-height: 1.5; }
.chunk-index { color: #6366f1; font-weight: 600; margin-right: 8px; }
.btn-more { background: none; border: 1px solid #e2e8f0; padding: 8px; border-radius: 8px; cursor: pointer; color: #6366f1; font-size: 13px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: white; padding: 24px; border-radius: 12px; width: 90%; max-width: 480px; }
.modal h3 { font-size: 18px; color: #1e293b; margin-bottom: 8px; }
.modal-desc { font-size: 13px; color: #64748b; margin-bottom: 16px; }
.modal textarea { width: 100%; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; resize: vertical; font-family: inherit; }
.modal textarea:focus { outline: none; border-color: #6366f1; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.btn-cancel-modal { padding: 10px 16px; background: #f1f5f9; border: none; border-radius: 8px; cursor: pointer; color: #64748b; }
@media (max-width: 768px) {
  .detail-layout { grid-template-columns: 1fr; }
  .version-sidebar { order: 2; }
  .detail-header { flex-direction: column; gap: 12px; }
}
</style>
