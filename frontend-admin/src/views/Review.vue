<template>
  <div>
    <div class="page-header">
      <h1>审核确认</h1>
      <p class="subtitle">对新版本进行审核：通过即发布并进入搜索与统计，退回需填写原因</p>
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
            <span class="version-badge">v{{ f.version_number }}</span>
            {{ f.name }}
          </div>
          <div class="file-meta">
            <span class="tag">{{ f.bucket }}</span>
            <span v-if="f.uploaded_by" class="meta-text">上传人：{{ f.uploaded_by }}</span>
            <span v-if="f.upload_date" class="meta-text">{{ formatDate(f.upload_date) }}</span>
          </div>
          <div v-if="f.change_note" class="change-note">📝 变更说明：{{ f.change_note }}</div>
        </div>
        <div class="suggestion">
          <label>AI建议标准名</label>
          <div class="value">{{ f.standard_name || '未生成' }}</div>
        </div>
        <div class="review-input-box">
          <label class="review-label">审核意见（退回时必填）</label>
          <input v-model="comments[f.id]" class="review-input" type="text" placeholder="如：分类错误 / 内容缺失，请补充后重新上传" />
        </div>
        <div class="actions">
          <button class="btn-approve" @click="review(f, 'approve')">✓ 通过并发布</button>
          <button class="btn-reject" @click="review(f, 'reject')">✗ 退回</button>
          <button v-if="f.document_id" class="btn-link" @click="$router.push(`/documents/${f.document_id}`)">查看版本历史</button>
        </div>
      </div>
    </div>
    <div v-else class="empty-card"><p>🎉 所有版本已审核完成</p></div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { files } from '../api'
import { useToast } from '../composables/useToast'
const toast = useToast()
const list = ref([])
const loading = ref(true)
const comments = ref({})

const formatDate = (s) => {
  if (!s) return ''
  const d = new Date(s)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const load = async () => {
  loading.value = true
  try {
    // 获取所有版本，筛选出待审核且处理完成的
    const { data } = await files.list({})
    list.value = (data.files || []).filter(f => f.review_status === 'pending' && f.status === 'completed')
  } catch { toast.error('加载审核列表失败'); list.value = [] }
  finally { loading.value = false }
}
const review = async (f, action) => {
  const comment = (comments.value[f.id] || '').trim()
  if (action === 'reject' && !comment) {
    toast.error('退回时请填写退回原因')
    return
  }
  try {
    await files.review(f.id, action, comment || null)
    toast.success(action === 'approve' ? '已通过并发布该版本' : '已退回该版本')
    delete comments.value[f.id]
    load()
  } catch (err) {
    toast.error(err?.response?.data?.detail || err?.response?.data?.message || '审核操作失败')
  }
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
.file-name { font-size: 16px; font-weight: 600; color: #1e293b; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.file-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.meta-text { font-size: 12px; color: #64748b; }
.change-note { margin-top: 10px; font-size: 13px; color: #334155; background: #f8fafc; padding: 8px 10px; border-radius: 6px; }
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.version-badge { background: #f1f5f9; color: #475569; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.suggestion { margin-bottom: 16px; }
.suggestion label { font-size: 12px; color: #64748b; text-transform: uppercase; }
.suggestion .value { margin-top: 8px; padding: 12px; background: #f8fafc; border-radius: 8px; font-family: monospace; }
.review-input-box { margin-bottom: 16px; }
.review-label { font-size: 12px; color: #64748b; display: block; margin-bottom: 6px; }
.review-input { width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; }
.review-input:focus { outline: none; border-color: #6366f1; }
.actions { display: flex; gap: 12px; flex-wrap: wrap; }
.btn-approve { padding: 10px 20px; background: #10b981; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-reject { padding: 10px 20px; background: white; color: #dc2626; border: 1px solid #fecaca; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-link { padding: 10px 20px; background: #f8fafc; color: #6366f1; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; font-size: 14px; }
.empty-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; }
.loading-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; border: 1px solid #e2e8f0; }
.loading-card p { margin-top: 16px; font-size: 15px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
