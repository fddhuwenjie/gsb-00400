<template>
  <div>
    <div class="page-header">
      <h1>知识检索</h1>
      <p class="subtitle">基于语义的智能文档搜索</p>
    </div>

    <div class="search-section">
      <div class="search-box">
        <input v-model="query" type="text" placeholder="输入关键词搜索..." @keyup.enter="doSearch" />
        <button @click="doSearch" :disabled="searching">{{ searching ? '搜索中...' : '搜索' }}</button>
      </div>
    </div>

    <div v-if="searching" class="loading-card">
      <div class="spinner"></div>
      <p>正在搜索中，请稍候...</p>
    </div>

    <div v-else-if="results.length" class="results">
      <p class="result-count">找到 {{ results.length }} 个相关文档（仅检索已发布版本）</p>
      <div
        v-for="r in results"
        :key="r.file_id"
        class="result-card"
        :class="{ clickable: r.document_id }"
        @click="r.document_id && $router.push(`/documents/${r.document_id}`)"
      >
        <div class="result-info">
          <div class="result-name">
            <span v-if="r.version_number" class="version-badge published">v{{ r.version_number }}</span>
            {{ r.filename }}
          </div>
          <div class="result-meta">
            <span v-if="r.bucket" class="tag">{{ r.bucket }}</span>
            <span v-if="r.standard_name">{{ r.standard_name }}</span>
          </div>
        </div>
        <div class="result-score">
          <div class="score">{{ (r.score * 100).toFixed(0) }}%</div>
          <div class="label">相关度</div>
        </div>
      </div>
    </div>
    <div v-else-if="searched" class="empty-card"><p>未找到相关文档</p></div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { search } from '../api'
import { useToast } from '../composables/useToast'
const toast = useToast()
const query = ref('')
const results = ref([])
const searched = ref(false)
const searching = ref(false)
const doSearch = async () => {
  if (!query.value) return
  searched.value = true; searching.value = true
  try { const { data } = await search.query(query.value); results.value = data.results || [] }
  catch { toast.error('搜索失败，请稍后重试'); results.value = [] }
  finally { searching.value = false }
}
</script>

<style scoped>
.page-header { background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 24px; }
h1 { font-size: 24px; color: #1e293b; }
.subtitle { color: #64748b; }
.search-section { background: #f8fafc; padding: 20px; border-radius: 12px; margin-bottom: 24px; }
.search-box { display: flex; gap: 12px; }
.search-box input { flex: 1; padding: 14px 20px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 16px; background: white; }
.search-box input:focus { outline: none; border-color: #6366f1; }
.search-box button { padding: 14px 28px; background: #6366f1; color: white; border: none; border-radius: 8px; cursor: pointer; }
.search-box button:disabled { background: #94a3b8; }
.results { display: flex; flex-direction: column; gap: 12px; }
.result-card { display: flex; justify-content: space-between; align-items: center; background: white; padding: 20px 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
.result-card.clickable { cursor: pointer; }
.result-card.clickable:hover { border-color: #c7d2fe; }
.result-name { font-size: 16px; font-weight: 500; color: #1e293b; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.version-badge { background: #f1f5f9; color: #475569; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.version-badge.published { background: #dcfce7; color: #166534; }
.tag { background: #e0e7ff; color: #4338ca; padding: 3px 10px; border-radius: 12px; font-size: 12px; }
.result-meta { font-size: 14px; color: #64748b; margin-top: 4px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.result-score { text-align: right; }
.score { font-size: 24px; font-weight: 700; color: #10b981; }
.label { font-size: 12px; color: #64748b; }
.empty-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; }
.loading-card { background: white; padding: 60px; border-radius: 12px; text-align: center; color: #64748b; border: 1px solid #e2e8f0; }
.loading-card p { margin-top: 16px; font-size: 15px; }
.spinner { width: 36px; height: 36px; border: 3px solid #e2e8f0; border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.result-count { font-size: 13px; color: #64748b; margin-bottom: 12px; }
@media (max-width: 768px) {
  .search-box { flex-direction: column; }
  .result-card { flex-direction: column; align-items: flex-start; gap: 12px; }
  .result-score { text-align: left; }
}
</style>
