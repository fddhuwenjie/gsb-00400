<template>
  <div>
    <div class="page-header">
      <div>
        <h1>文件管理</h1>
        <p>上传和管理知识库文件，同一业务文档重复上传将自动生成新版本</p>
      </div>
      <div class="upload-area">
        <input v-model="changeNote" class="note-input" type="text" placeholder="变更说明（可选，如：更新第三章部署流程）" />
        <label class="btn-upload">
          📤 上传文件
          <input type="file" multiple @change="upload" hidden />
        </label>
      </div>
    </div>

    <div class="upload-progress" :class="{ active: uploading }">
      <div class="progress-label">上传中... {{ uploadPercent }}%</div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: uploadPercent + '%' }"></div>
      </div>
    </div>

    <div class="filter-bar">
      <select v-model="filter.bucket" @change="onFilterChange">
        <option value="">全部分类</option>
        <option value="方案">方案</option>
        <option value="彩页">彩页</option>
        <option value="视频">视频</option>
        <option value="安装包">安装包</option>
      </select>
      <select v-model="filter.status" @change="onFilterChange">
        <option value="">全部状态</option>
        <option value="published">已发布</option>
        <option value="pending">待审核</option>
      </select>
      <button @click="onRefresh" class="btn-refresh">🔄 刷新</button>
    </div>

    <div class="card">
      <table v-if="pagedList.length" class="desktop-table">
        <thead><tr><th>文档名称</th><th>分类</th><th>最新版本</th><th>已发布</th><th>版本数</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="d in pagedList" :key="d.id" class="doc-row" @click="openDoc(d.id)">
            <td>{{ d.title || d.doc_key }}</td>
            <td><span class="tag">{{ d.bucket || '-' }}</span></td>
            <td><span class="version-badge">v{{ d.current_version }}</span></td>
            <td>
              <span v-if="d.published_version" class="version-badge published">v{{ d.published_version }}</span>
              <span v-else class="muted">未发布</span>
            </td>
            <td>{{ d.version_count }}</td>
            <td>
              <span v-if="d.has_pending" :class="['status', 'pending']">待审核</span>
              <span v-else-if="d.published_version" :class="['status', 'approved']">已发布</span>
              <span v-else :class="['status', 'processing']">处理中</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="pagedList.length" class="mobile-cards">
        <div v-for="d in pagedList" :key="'m'+d.id" class="file-card" @click="openDoc(d.id)">
          <div class="file-card-name">{{ d.title || d.doc_key }}</div>
          <div class="file-card-meta">
            <span class="tag">{{ d.bucket || '-' }}</span>
            <span class="version-badge">最新 v{{ d.current_version }}</span>
            <span v-if="d.published_version" class="version-badge published">已发布 v{{ d.published_version }}</span>
            <span v-if="d.has_pending" :class="['status', 'pending']">待审核</span>
            <span v-else-if="d.published_version" :class="['status', 'approved']">已发布</span>
          </div>
          <div class="file-card-sub">共 {{ d.version_count }} 个版本，点击查看版本历史</div>
        </div>
      </div>
      <div v-if="!list.length" class="empty">暂无文档，请上传</div>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button @click="goPage(1)" :disabled="page === 1">首页</button>
        <button @click="goPage(page - 1)" :disabled="page === 1">上一页</button>
        <span class="page-info">第 {{ page }} / {{ totalPages }} 页，共 {{ list.length }} 篇文档</span>
        <button @click="goPage(page + 1)" :disabled="page === totalPages">下一页</button>
        <button @click="goPage(totalPages)" :disabled="page === totalPages">末页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { documents, files } from '../api'
import { useToast } from '../composables/useToast'

const router = useRouter()
const toast = useToast()
const list = ref([])
const filter = reactive({ bucket: '', status: '' })
const uploading = ref(false)
const uploadPercent = ref(0)
const changeNote = ref('')
const page = ref(1)
const pageSize = 10

const totalPages = computed(() => Math.ceil(list.value.length / pageSize) || 1)
const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize
  return list.value.slice(start, start + pageSize)
})

const goPage = (p) => {
  if (p >= 1 && p <= totalPages.value) page.value = p
}

const openDoc = (id) => router.push(`/documents/${id}`)

const load = async (toastMsg = '') => {
  const params = {}
  if (filter.bucket) params.bucket = filter.bucket
  if (filter.status) params.status = filter.status
  try {
    const { data } = await documents.list(params)
    const newList = data.documents || []
    list.value = newList
    if (page.value > Math.ceil(newList.length / pageSize)) page.value = 1
    if (toastMsg) toast.success(toastMsg)
  } catch (err) {
    toast.error('加载文档列表失败')
  }
}

const onFilterChange = () => load('查询成功')
const onRefresh = () => load('刷新成功')

const upload = async (e) => {
  const fd = new FormData()
  for (const f of e.target.files) fd.append('files', f)
  const extra = {}
  if (changeNote.value.trim()) extra.change_note = changeNote.value.trim()
  uploading.value = true
  uploadPercent.value = 0
  try {
    const { data } = await files.upload(fd, (p) => { uploadPercent.value = p }, extra)
    const newDocCount = data.files.filter(f => f.is_new_document).length
    const versionCount = data.files.length - newDocCount
    toast.success(`上传成功：${newDocCount} 篇新文档，${versionCount} 个新版本`)
    changeNote.value = ''
    setTimeout(load, 500)
  } catch (err) {
    toast.error('文件上传失败')
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; gap: 16px; flex-wrap: wrap; }
h1 { font-size: 24px; color: #1e293b; }
p { color: #64748b; font-size: 14px; margin-top: 4px; }
.upload-area { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.note-input { padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 260px; }
.note-input:focus { outline: none; border-color: #6366f1; }
.btn-upload { padding: 10px 20px; background: #6366f1; color: white; border-radius: 8px; cursor: pointer; font-size: 14px; white-space: nowrap; }
.upload-progress { background: white; padding: 0 24px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 16px; max-height: 0; overflow: hidden; opacity: 0; transition: max-height 0.3s ease, opacity 0.3s ease, padding 0.3s ease; border-color: transparent; }
.upload-progress.active { max-height: 80px; opacity: 1; padding: 16px 24px; border-color: #e2e8f0; }
.progress-label { font-size: 14px; color: #1e293b; margin-bottom: 8px; font-weight: 500; }
.progress-bar { height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #6366f1, #818cf8); border-radius: 4px; transition: width 0.3s ease; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 20px; background: #f8fafc; padding: 16px; border-radius: 12px; flex-wrap: wrap; }
.filter-bar select { padding: 10px 32px 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; background: white; font-size: 14px; appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2364748b' d='M2 4l4 4 4-4'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; cursor: pointer; }
.btn-refresh { padding: 10px 16px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; }
.card { background: white; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; min-height: 200px; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 14px 16px; font-size: 12px; color: #64748b; border-bottom: 1px solid #e2e8f0; text-transform: uppercase; }
td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; }
.doc-row { cursor: pointer; }
.doc-row:hover { background: #f8fafc; }
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.version-badge { background: #f1f5f9; color: #475569; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.version-badge.published { background: #dcfce7; color: #166534; }
.muted { color: #94a3b8; font-size: 13px; }
.status { padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status.pending { background: #f1f5f9; color: #64748b; }
.status.processing { background: #fef3c7; color: #92400e; }
.status.completed, .status.approved { background: #dcfce7; color: #166534; }
.status.failed, .status.rejected { background: #fee2e2; color: #991b1b; }
.empty { padding: 60px; text-align: center; color: #94a3b8; }
.mobile-cards { display: none; }
.file-card { padding: 16px; border-bottom: 1px solid #f1f5f9; cursor: pointer; }
.file-card:active { background: #f8fafc; }
.file-card-name { font-weight: 600; color: #1e293b; margin-bottom: 8px; word-break: break-all; }
.file-card-sub { font-size: 12px; color: #94a3b8; margin-top: 8px; }
.file-card-meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 16px; border-top: 1px solid #e2e8f0; }
.pagination button { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; }
.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
.pagination button:not(:disabled):hover { background: #f8fafc; }
.page-info { font-size: 13px; color: #64748b; margin: 0 8px; }
@media (max-width: 768px) {
  .desktop-table { display: none; }
  .mobile-cards { display: block; }
  .page-header { flex-direction: column; }
  .note-input { min-width: 0; width: 100%; }
  .pagination { flex-wrap: wrap; }
}
</style>
