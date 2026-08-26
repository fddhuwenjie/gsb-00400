<template>
  <div>
    <div class="page-header">
      <div>
        <h1>文件管理</h1>
        <p>上传和管理知识库文件，同业务文档自动版本化</p>
      </div>
      <div class="header-actions">
        <button class="btn-toggle-mode" @click="toggleMode">
          {{ viewMode === 'files' ? '📚 按文档查看' : '📄 按版本查看' }}
        </button>
        <label class="btn-upload">
          📤 上传文件
          <input type="file" multiple @change="upload" hidden />
        </label>
      </div>
    </div>

    <div v-if="showChangeDesc" class="change-desc-bar">
      <input
        v-model="pendingChangeDesc"
        type="text"
        placeholder="输入本次上传的变更说明（可选，如：更新第三章参数表）"
        @keyup.enter="confirmUpload"
      />
      <button class="btn-confirm" @click="confirmUpload">确认上传</button>
      <button class="btn-cancel" @click="cancelUpload">取消</button>
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
      <select v-if="viewMode === 'files'" v-model="filter.status" @change="onFilterChange">
        <option value="">全部状态</option>
        <option value="pending">待处理</option>
        <option value="processing">处理中</option>
        <option value="completed">已完成</option>
        <option value="failed">失败</option>
      </select>
      <select v-if="viewMode === 'files'" v-model="filter.review_status" @change="onFilterChange">
        <option value="">全部审核状态</option>
        <option value="pending">待审核</option>
        <option value="approved">已通过</option>
        <option value="rejected">已拒绝</option>
      </select>
      <button @click="onRefresh" class="btn-refresh">🔄 刷新</button>
    </div>

    <!-- 按文档视图 -->
    <div v-if="viewMode === 'documents'" class="card">
      <table v-if="pagedDocs.length" class="desktop-table">
        <thead>
          <tr><th>文档标题</th><th>分类</th><th>版本数</th><th>当前版本</th><th>最新版本</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in pagedDocs" :key="d.id">
            <td>{{ d.title }}</td>
            <td><span class="tag">{{ d.bucket || '-' }}</span></td>
            <td>{{ d.version_count }}</td>
            <td>
              <span v-if="d.current_version" class="version-badge current">v{{ d.current_version }}</span>
              <span v-else class="muted">未发布</span>
            </td>
            <td>
              <span :class="['version-badge', d.current_version === d.latest_version ? 'current' : 'pending']">
                v{{ d.latest_version }}
              </span>
            </td>
            <td>
              <router-link :to="`/documents/${d.id}`" class="btn-link">查看版本</router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="pagedDocs.length" class="mobile-cards">
        <div v-for="d in pagedDocs" :key="'m'+d.id" class="file-card">
          <div class="file-card-name">{{ d.title }}</div>
          <div class="file-card-meta">
            <span class="tag">{{ d.bucket || '-' }}</span>
            <span class="version-badge current" v-if="d.current_version">v{{ d.current_version }}</span>
            <span class="version-badge pending" v-if="d.current_version !== d.latest_version">v{{ d.latest_version }}</span>
            <span class="muted">共 {{ d.version_count }} 版</span>
          </div>
          <router-link :to="`/documents/${d.id}`" class="btn-link">查看版本</router-link>
        </div>
      </div>
      <div v-if="!docs.length" class="empty">暂无文档，请上传</div>
    </div>

    <!-- 按版本视图 -->
    <div v-else class="card">
      <table v-if="pagedList.length" class="desktop-table">
        <thead>
          <tr><th>文件名</th><th>版本</th><th>标准名</th><th>分类</th><th>状态</th><th>审核</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="f in pagedList" :key="f.id">
            <td>{{ f.name }}</td>
            <td>
              <span :class="['version-badge', f.is_current ? 'current' : 'old']">v{{ f.version_number }}</span>
              <span v-if="f.is_current" class="current-tag">当前</span>
            </td>
            <td>{{ f.standard_name || '-' }}</td>
            <td><span class="tag">{{ f.bucket }}</span></td>
            <td><span :class="['status', f.status]">{{ statusMap[f.status] }}</span></td>
            <td><span :class="['status', f.review_status]">{{ reviewMap[f.review_status] }}</span></td>
            <td>
              <router-link v-if="f.document_id" :to="`/documents/${f.document_id}`" class="btn-link">版本历史</router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="pagedList.length" class="mobile-cards">
        <div v-for="f in pagedList" :key="'m'+f.id" class="file-card">
          <div class="file-card-name">
            {{ f.name }}
            <span :class="['version-badge', f.is_current ? 'current' : 'old']">v{{ f.version_number }}</span>
          </div>
          <div class="file-card-std">{{ f.standard_name || '-' }}</div>
          <div class="file-card-meta">
            <span class="tag">{{ f.bucket }}</span>
            <span :class="['status', f.status]">{{ statusMap[f.status] }}</span>
            <span :class="['status', f.review_status]">{{ reviewMap[f.review_status] }}</span>
          </div>
          <router-link v-if="f.document_id" :to="`/documents/${f.document_id}`" class="btn-link">版本历史</router-link>
        </div>
      </div>
      <div v-if="!list.length" class="empty">暂无文件，请上传</div>
    </div>

    <div v-if="totalPages > 1" class="pagination">
      <button @click="goPage(1)" :disabled="page === 1">首页</button>
      <button @click="goPage(page - 1)" :disabled="page === 1">上一页</button>
      <span class="page-info">第 {{ page }} / {{ totalPages }} 页，共 {{ currentCount }} 条</span>
      <button @click="goPage(page + 1)" :disabled="page === totalPages">下一页</button>
      <button @click="goPage(totalPages)" :disabled="page === totalPages">末页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { files, documents } from '../api'
import { useToast } from '../composables/useToast'

const toast = useToast()
const list = ref([])
const docs = ref([])
const filter = reactive({ bucket: '', status: '', review_status: '' })
const uploading = ref(false)
const uploadPercent = ref(0)
const page = ref(1)
const pageSize = 10
const viewMode = ref('documents')
const showChangeDesc = ref(false)
const pendingChangeDesc = ref('')
let pendingFiles = null

const statusMap = { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }
const reviewMap = { pending: '待审核', approved: '已通过', rejected: '已拒绝' }

const currentData = computed(() => viewMode.value === 'documents' ? docs.value : list.value)
const currentCount = computed(() => currentData.value.length)
const totalPages = computed(() => Math.ceil(currentCount.value / pageSize) || 1)
const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize
  return list.value.slice(start, start + pageSize)
})
const pagedDocs = computed(() => {
  const start = (page.value - 1) * pageSize
  return docs.value.slice(start, start + pageSize)
})

const goPage = (p) => {
  if (p >= 1 && p <= totalPages.value) page.value = p
}

const load = async (toastMsg = '') => {
  try {
    if (viewMode.value === 'documents') {
      const params = {}
      if (filter.bucket) params.bucket = filter.bucket
      const { data } = await documents.list(params)
      docs.value = data.documents || []
    } else {
      const params = {}
      if (filter.bucket) params.bucket = filter.bucket
      if (filter.status) params.status = filter.status
      if (filter.review_status) params.review_status = filter.review_status
      const { data } = await files.list(params)
      list.value = data.files || []
    }
    if (page.value > totalPages.value) page.value = 1
    if (toastMsg) toast.success(toastMsg)
  } catch (err) {
    toast.error('加载失败')
  }
}

const onFilterChange = () => load('查询成功')
const onRefresh = () => load('刷新成功')
const toggleMode = () => {
  viewMode.value = viewMode.value === 'files' ? 'documents' : 'files'
  page.value = 1
  load()
}

const upload = (e) => {
  pendingFiles = e.target.files
  if (!pendingFiles || !pendingFiles.length) return
  showChangeDesc.value = true
  pendingChangeDesc.value = ''
}

const cancelUpload = () => {
  showChangeDesc.value = false
  pendingFiles = null
  pendingChangeDesc.value = ''
}

const confirmUpload = async () => {
  if (!pendingFiles) return
  const fd = new FormData()
  for (const f of pendingFiles) fd.append('files', f)
  if (pendingChangeDesc.value) fd.append('change_description', pendingChangeDesc.value)
  showChangeDesc.value = false
  uploading.value = true
  uploadPercent.value = 0
  try {
    const { data } = await files.upload(fd, (p) => { uploadPercent.value = p })
    const newDocs = data.files.filter(f => f.is_new_document).length
    const newVersions = data.files.length - newDocs
    let msg = `成功上传 ${data.uploaded} 个文件`
    if (newVersions > 0) msg += `（${newVersions} 个新版本）`
    toast.success(msg)
    setTimeout(load, 500)
  } catch (err) {
    toast.error('文件上传失败')
  } finally {
    uploading.value = false
    pendingFiles = null
    pendingChangeDesc.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
.header-actions { display: flex; gap: 12px; }
h1 { font-size: 24px; color: #1e293b; }
p { color: #64748b; font-size: 14px; margin-top: 4px; }
.btn-upload { padding: 10px 20px; background: #6366f1; color: white; border-radius: 8px; cursor: pointer; font-size: 14px; display: inline-block; }
.btn-toggle-mode { padding: 10px 16px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; font-size: 14px; color: #475569; }
.btn-toggle-mode:hover { background: #f8fafc; }
.change-desc-bar { display: flex; gap: 12px; margin-bottom: 16px; background: white; padding: 16px; border-radius: 12px; border: 1px solid #e2e8f0; }
.change-desc-bar input { flex: 1; padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; }
.change-desc-bar input:focus { outline: none; border-color: #6366f1; }
.btn-confirm { padding: 10px 20px; background: #10b981; color: white; border: none; border-radius: 8px; cursor: pointer; }
.btn-cancel { padding: 10px 20px; background: #f1f5f9; color: #64748b; border: none; border-radius: 8px; cursor: pointer; }
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
td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status { padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status.pending { background: #f1f5f9; color: #64748b; }
.status.processing { background: #fef3c7; color: #92400e; }
.status.completed, .status.approved { background: #dcfce7; color: #166534; }
.status.failed, .status.rejected { background: #fee2e2; color: #991b1b; }
.version-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.version-badge.current { background: #dbeafe; color: #1e40af; }
.version-badge.old { background: #f1f5f9; color: #64748b; }
.version-badge.pending { background: #fef3c7; color: #92400e; }
.current-tag { font-size: 11px; color: #2563eb; margin-left: 4px; }
.muted { color: #94a3b8; font-size: 12px; }
.btn-link { color: #6366f1; text-decoration: none; font-size: 13px; }
.btn-link:hover { text-decoration: underline; }
.empty { padding: 60px; text-align: center; color: #94a3b8; }
.mobile-cards { display: none; }
.file-card { padding: 16px; border-bottom: 1px solid #f1f5f9; }
.file-card-name { font-weight: 600; color: #1e293b; margin-bottom: 4px; word-break: break-all; display: flex; align-items: center; gap: 8px; }
.file-card-std { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.file-card-meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 16px; margin-top: 16px; }
.pagination button { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; }
.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
.pagination button:not(:disabled):hover { background: #f8fafc; }
.page-info { font-size: 13px; color: #64748b; margin: 0 8px; }
@media (max-width: 768px) {
  .desktop-table { display: none; }
  .mobile-cards { display: block; }
  .page-header { flex-direction: column; gap: 12px; }
  .header-actions { width: 100%; }
  .btn-upload, .btn-toggle-mode { flex: 1; text-align: center; }
  .pagination { flex-wrap: wrap; }
  .change-desc-bar { flex-direction: column; }
}
</style>
