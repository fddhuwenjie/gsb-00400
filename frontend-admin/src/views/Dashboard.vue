<template>
  <div>
    <div class="page-header">
      <h1>数据总览</h1>
      <p class="subtitle">知识库系统运行状态</p>
    </div>

    <div class="stats">
      <div class="stat-card blue"><div class="stat-value">{{ data.total_documents ?? 0 }}</div><div class="stat-label">业务文档数</div></div>
      <div class="stat-card green"><div class="stat-value">{{ data.total_versions ?? data.total_files ?? 0 }}</div><div class="stat-label">版本总数</div></div>
      <div class="stat-card orange"><div class="stat-value">{{ data.pending_review }}</div><div class="stat-label">待审核版本</div></div>
      <div class="stat-card purple"><div class="stat-value">{{ data.published ?? data.approved }}</div><div class="stat-label">已发布版本</div></div>
    </div>

    <div class="actions-bar">
      <button class="btn-action" @click="processPending" :disabled="loading">
        {{ loading ? '处理中...' : '⚡ 处理待处理文件' }}
      </button>
      <button class="btn-action" @click="reindex" :disabled="loading">
        {{ loading ? '索引中...' : '🔄 重建向量索引' }}
      </button>
    </div>

    <div class="grid">
      <div class="card">
        <h3>分类统计 <span class="card-note">（仅已发布版本）</span></h3>
        <div v-for="(count, bucket) in data.by_bucket" :key="bucket" class="bucket-row">
          <span>{{ bucket }}</span><span class="count">{{ count }}</span>
        </div>
        <div v-if="!Object.keys(data.by_bucket || {}).length" class="empty">暂无数据</div>
      </div>
      <div class="card">
        <h3>热门标签</h3>
        <div class="tags">
          <span v-for="t in tags" :key="t.value" class="tag">{{ t.value }} ({{ t.count }})</span>
        </div>
        <div v-if="!tags.length" class="empty">暂无标签</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { stats, files } from '../api'
import { useToast } from '../composables/useToast'
const toast = useToast()
const data = ref({ total_files: 0, total_documents: 0, total_versions: 0, completed: 0, pending_review: 0, approved: 0, published: 0, by_bucket: {} })
const tags = ref([])
const loading = ref(false)
const refresh = async () => {
  const [o, t] = await Promise.all([stats.overview(), stats.tags()])
  data.value = o.data; tags.value = t.data.tags.slice(0, 15)
}
const reindex = async () => {
  loading.value = true
  try { const r = await files.reindex(); toast.success('已索引 ' + r.data.indexed_files + ' 个文件') }
  catch { toast.error('索引失败，请稍后重试') }
  loading.value = false
}
const processPending = async () => {
  loading.value = true
  try {
    const r = await files.processPending()
    toast.success('已处理 ' + r.data.processed + ' 个文件')
    if (r.data.errors?.length) toast.warning(r.data.errors.length + ' 个文件处理失败')
    await refresh()
  } catch { toast.error('处理失败，请稍后重试') }
  loading.value = false
}
onMounted(refresh)
</script>

<style scoped>
.page-header { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 24px; }
h1 { font-size: 24px; color: #1e293b; }
.subtitle { color: #64748b; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; border-left: 4px solid #e2e8f0; }
.stat-card.blue { border-left-color: #3b82f6; }
.stat-card.green { border-left-color: #10b981; }
.stat-card.orange { border-left-color: #f59e0b; }
.stat-card.purple { border-left-color: #8b5cf6; }
.stat-value { font-size: 32px; font-weight: 700; color: #1e293b; }
.stat-label { color: #64748b; font-size: 14px; margin-top: 4px; }
.actions-bar { margin-bottom: 24px; display: flex; gap: 12px; background: #f8fafc; padding: 16px; border-radius: 12px; flex-wrap: wrap; }
.btn-action { padding: 12px 20px; background: #6366f1; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-action:disabled { background: #94a3b8; cursor: not-allowed; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
.card h3 { font-size: 16px; color: #1e293b; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; }
.card-note { font-size: 12px; color: #94a3b8; font-weight: 400; }
.bucket-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.count { color: #6366f1; font-weight: 600; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; }
.tag { background: #e0e7ff; color: #4338ca; padding: 6px 12px; border-radius: 16px; font-size: 13px; }
.empty { color: #94a3b8; text-align: center; padding: 20px; }
@media (max-width: 768px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .grid { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .stats { grid-template-columns: 1fr; }
}
</style>
