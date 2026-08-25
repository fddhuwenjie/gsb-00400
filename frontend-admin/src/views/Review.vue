<template>
  <div>
    <div class="page-header">
      <h1>审核确认</h1>
      <p class="subtitle">确认AI生成的分类和标签</p>
    </div>

    <div v-if="loading" class="loading-card">
      <div class="spinner"></div>
      <p>加载审核列表中...</p>
    </div>

    <div v-else-if="list.length" class="review-list">
      <p class="review-count">共 {{ list.length }} 个版本待审核</p>
      <div v-for="f in list" :key="f.id" class="review-card">
        <div class="file-info">
          <div class="file-name">
            {{ f.name }}
            <span v-if="f.version_no" class="version-badge">v{{ f.version_no }}</span>
          </div>
          <div class="file-meta">
            <span class="tag">{{ f.bucket }}</span>
            <span :class="['status-tag', f.status]">{{ statusMap[f.status] || f.status }}</span>
            <button v-if="f.group_id" class="btn-history" @click="openVersions(f.group_id)">切换版本</button>
          </div>
        </div>
        <div v-if="f.change_note" class="suggestion">
          <label>变更说明</label>
          <div class="value">{{ f.change_note }}</div>
        </div>
        <div class="suggestion">
          <label>AI建议标准名</label>
          <div class="value">{{ f.standard_name || '未生成' }}</div>
        </div>
        <div class="actions">
          <button class="btn-approve" @click="review(f.id, 'approve')">✓ 通过并发布</button>
          <button class="btn-reject" @click="review(f.id, 'reject')">✗ 退回</button>
        </div>
      </div>
    </div>
    <div v-else class="empty-card"><p>🎉 所有版本已审核完成</p></div>

    <!-- 版本切换弹窗 -->
    <div v-if="versionModal.open" class="modal-overlay" @click.self="closeVersions">
      <div class="modal">
        <div class="modal-header">
          <h3>版本切换 · {{ versionModal.group?.title }}</h3>
          <button class="modal-close" @click="closeVersions">✕</button>
        </div>
        <div class="modal-body">
          <p v-if="versionModal.loading" class="hint">加载中...</p>
          <div v-else-if="versionModal.versions.length" class="version-list">
            <div v-for="v in versionModal.versions" :key="v.id" class="version-item" :class="{ published: v.is_published }">
              <div class="version-head">
                <span class="version-badge">v{{ v.version_no }}</span>
                <span :class="['status-tag', v.review_status]">{{ reviewMap[v.review_status] }}</span>
                <span v-if="v.is_published" class="published-badge">当前发布</span>
              </div>
              <div class="version-detail">
                <span>上传人：{{ v.uploaded_by_name || '-' }}</span>
                <span>时间：{{ formatTime(v.upload_date) }}</span>
              </div>
              <div v-if="v.change_note" class="version-note">变更：{{ v.change_note }}</div>
              <div class="version-actions">
                <button class="btn-approve sm" @click="reviewFromModal(v.id, 'approve')">通过并发布</button>
                <button class="btn-reject sm" @click="reviewFromModal(v.id, 'reject')">退回</button>
              </div>
            </div>
          </div>
          <p v-else class="hint">暂无版本</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { files } from '../api'
import { useToast } from '../composables/useToast'
const toast = useToast()
const list = ref([])
const loading = ref(true)
const statusMap = { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }
const reviewMap = { pending: '待审核', approved: '已通过', rejected: '已退回' }
const versionModal = reactive({ open: false, loading: false, group: null, versions: [] })

const formatTime = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return isNaN(d) ? iso : d.toLocaleString()
}

const load = async () => {
  loading.value = true
  try {
    // 获取全部版本，筛选出待审核的（不限处理状态）
    const { data } = await files.list({ all_versions: true })
    list.value = (data.files || []).filter(f => f.review_status === 'pending')
  } catch { toast.error('加载审核列表失败'); list.value = [] }
  finally { loading.value = false }
}
const review = async (id, action) => {
  try {
    await files.review(id, action)
    toast.success(action === 'approve' ? '已通过并发布' : '已退回')
    load()
  } catch { toast.error('审核操作失败') }
}
const openVersions = async (groupId) => {
  versionModal.open = true
  versionModal.loading = true
  versionModal.versions = []
  versionModal.group = null
  try {
    const { data } = await files.versions(groupId)
    versionModal.group = data.group
    versionModal.versions = data.versions || []
  } catch { toast.error('加载版本历史失败') }
  finally { versionModal.loading = false }
}
const closeVersions = () => { versionModal.open = false }
const reviewFromModal = async (id, action) => {
  try {
    await files.review(id, action)
    toast.success(action === 'approve' ? '已通过并发布' : '已退回')
    await openVersions(versionModal.group.group_id)
    await load()
  } catch { toast.error('审核操作失败') }
}
onMounted(load)
</script>

<style scoped>
.page-header { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 24px; }
h1 { font-size: 24px; color: #1e293b; }
.subtitle { color: #64748b; }
.review-list { display: flex; flex-direction: column; gap: 16px; }
.review-count { font-size: 13px; color: #64748b; margin-bottom: 4px; }
.review-card { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
.file-info { margin-bottom: 16px; }
.file-name { font-size: 16px; font-weight: 600; color: #1e293b; margin-bottom: 8px; }
.file-meta { display: flex; gap: 8px; align-items: center; }
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status-tag { padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status-tag.completed { background: #dcfce7; color: #166534; }
.status-tag.failed { background: #fee2e2; color: #991b1b; }
.status-tag.pending { background: #f1f5f9; color: #64748b; }
.status-tag.processing { background: #fef3c7; color: #92400e; }
.suggestion { margin-bottom: 16px; }
.suggestion label { font-size: 12px; color: #64748b; text-transform: uppercase; }
.suggestion .value { margin-top: 8px; padding: 12px; background: #f8fafc; border-radius: 8px; font-family: monospace; }
.actions { display: flex; gap: 12px; }
.btn-approve { padding: 10px 20px; background: #10b981; color: white; border: none; border-radius: 8px; cursor: pointer; }
.btn-reject { padding: 10px 20px; background: #f1f5f9; color: #64748b; border: none; border-radius: 8px; cursor: pointer; }
.empty-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; }
.loading-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; border: 1px solid #e2e8f0; }
.loading-card p { margin-top: 16px; font-size: 15px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.status-tag.approved { background: #dcfce7; color: #166534; }
.status-tag.rejected { background: #fee2e2; color: #991b1b; }
.version-badge { display: inline-block; margin-left: 8px; background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; vertical-align: middle; }
.btn-history { background: none; border: 1px solid #e2e8f0; color: #6366f1; cursor: pointer; font-size: 12px; padding: 4px 10px; border-radius: 8px; }
.btn-history:hover { background: #f8fafc; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1100; display: flex; align-items: center; justify-content: center; padding: 16px; }
.modal { background: white; border-radius: 12px; width: 100%; max-width: 640px; max-height: 80vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #e2e8f0; }
.modal-header h3 { font-size: 16px; color: #1e293b; }
.modal-close { background: none; border: none; font-size: 18px; cursor: pointer; color: #64748b; }
.modal-body { padding: 16px 24px; overflow: auto; }
.version-list { display: flex; flex-direction: column; gap: 12px; }
.version-item { border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; }
.version-item.published { background: #f0fdf4; border-color: #86efac; }
.version-head { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.version-detail { display: flex; gap: 16px; font-size: 13px; color: #64748b; margin-bottom: 4px; }
.version-note { font-size: 13px; color: #475569; margin-bottom: 8px; }
.version-actions { display: flex; gap: 8px; }
.published-badge { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.btn-approve.sm, .btn-reject.sm { padding: 6px 12px; font-size: 13px; }
.hint { color: #64748b; font-size: 14px; }
</style>
