<template>
  <div>
    <div class="page-header">
      <div>
        <h1>文件管理</h1>
        <p>上传和管理知识库文件</p>
      </div>
      <label class="btn-upload">
        📤 上传文件
        <input type="file" multiple @change="onFilesPicked" hidden ref="fileInput" />
      </label>
    </div>

    <!-- 上传设置：文档标识与变更说明（用于版本化） -->
    <div v-if="pendingFiles.length" class="upload-form card">
      <h3>上传设置（版本化）</h3>
      <p class="hint">已选择 {{ pendingFiles.length }} 个文件。填写「文档标识」可将本次上传作为同一业务文档的新版本，旧版本不会被覆盖。</p>
      <div class="form-row">
        <label>文档标识 (doc_key)</label>
        <input v-model="uploadForm.docKey" type="text" placeholder="留空则按文件名各自建档" />
      </div>
      <div class="form-row">
        <label>变更说明</label>
        <input v-model="uploadForm.changeNote" type="text" placeholder="本次版本的变更内容" />
      </div>
      <div class="form-actions">
        <button class="btn-primary" @click="doUpload" :disabled="uploading">确认上传</button>
        <button class="btn-cancel" @click="cancelUpload" :disabled="uploading">取消</button>
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
        <option value="pending">待处理</option>
        <option value="processing">处理中</option>
        <option value="completed">已完成</option>
        <option value="failed">失败</option>
      </select>
      <button @click="onRefresh" class="btn-refresh">🔄 刷新</button>
    </div>

    <div class="card">
      <table v-if="pagedList.length" class="desktop-table">
        <thead><tr><th>文件名</th><th>标准名</th><th>分类</th><th>版本</th><th>状态</th><th>审核</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="f in pagedList" :key="f.id">
            <td>{{ f.name }}</td><td>{{ f.standard_name || '-' }}</td>
            <td><span class="tag">{{ f.bucket }}</span></td>
            <td><span v-if="f.version_no" class="version-badge">v{{ f.version_no }}</span><span v-else>-</span></td>
            <td><span :class="['status', f.status]">{{ statusMap[f.status] }}</span></td>
            <td><span :class="['status', f.review_status]">{{ reviewMap[f.review_status] }}</span></td>
            <td>
              <button v-if="f.group_id" class="btn-link" @click="openVersions(f.group_id)">版本历史</button>
              <span v-else>-</span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="pagedList.length" class="mobile-cards">
        <div v-for="f in pagedList" :key="'m'+f.id" class="file-card">
          <div class="file-card-name">{{ f.name }}</div>
          <div class="file-card-std">{{ f.standard_name || '-' }}</div>
          <div class="file-card-meta">
            <span class="tag">{{ f.bucket }}</span>
            <span v-if="f.version_no" class="version-badge">v{{ f.version_no }}</span>
            <span :class="['status', f.status]">{{ statusMap[f.status] }}</span>
            <span :class="['status', f.review_status]">{{ reviewMap[f.review_status] }}</span>
          </div>
          <button v-if="f.group_id" class="btn-link" @click="openVersions(f.group_id)">版本历史</button>
        </div>
      </div>
      <div v-if="!list.length" class="empty">暂无文件，请上传</div>
      
      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button @click="goPage(1)" :disabled="page === 1">首页</button>
        <button @click="goPage(page - 1)" :disabled="page === 1">上一页</button>
        <span class="page-info">第 {{ page }} / {{ totalPages }} 页，共 {{ list.length }} 条</span>
        <button @click="goPage(page + 1)" :disabled="page === totalPages">下一页</button>
        <button @click="goPage(totalPages)" :disabled="page === totalPages">末页</button>
      </div>
    </div>

    <!-- 版本历史弹窗 -->
    <div v-if="versionModal.open" class="modal-overlay" @click.self="closeVersions">
      <div class="modal">
        <div class="modal-header">
          <h3>版本历史 · {{ versionModal.group?.title }}</h3>
          <button class="modal-close" @click="closeVersions">✕</button>
        </div>
        <div class="modal-body">
          <p v-if="versionModal.loading" class="hint">加载中...</p>
          <table v-else-if="versionModal.versions.length" class="version-table">
            <thead><tr><th>版本</th><th>上传人</th><th>上传时间</th><th>变更说明</th><th>审核</th><th>发布</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="v in versionModal.versions" :key="v.id" :class="{ published: v.is_published }">
                <td>v{{ v.version_no }}</td>
                <td>{{ v.uploaded_by_name || '-' }}</td>
                <td>{{ formatTime(v.upload_date) }}</td>
                <td class="note">{{ v.change_note || '-' }}</td>
                <td><span :class="['status', v.review_status]">{{ reviewMap[v.review_status] }}</span></td>
                <td>
                  <span v-if="v.is_published" class="published-badge">当前发布</span>
                  <span v-else>-</span>
                </td>
                <td><button class="btn-link" @click="openDetail(v.id)">查看详情</button></td>
              </tr>
            </tbody>
          </table>
          <p v-else class="hint">暂无版本</p>
        </div>
      </div>
    </div>

    <!-- 版本详情弹窗：旧版本内容仍可查看 -->
    <div v-if="detailModal.open" class="modal-overlay" @click.self="closeDetail">
      <div class="modal">
        <div class="modal-header">
          <h3>
            版本详情
            <span v-if="detailModal.version" class="version-badge">v{{ detailModal.version.version_no }}</span>
          </h3>
          <button class="modal-close" @click="closeDetail">✕</button>
        </div>
        <div class="modal-body">
          <p v-if="detailModal.loading" class="hint">加载中...</p>
          <div v-else-if="detailModal.version">
            <div class="detail-grid">
              <div><label>文件名</label><span>{{ detailModal.version.original_name }}</span></div>
              <div><label>标准名</label><span>{{ detailModal.version.standard_name || '-' }}</span></div>
              <div><label>分类</label><span>{{ detailModal.version.bucket }}</span></div>
              <div><label>上传人</label><span>{{ detailModal.version.uploaded_by_name || '-' }}</span></div>
              <div><label>上传时间</label><span>{{ formatTime(detailModal.version.upload_date) }}</span></div>
              <div><label>审核状态</label><span :class="['status', detailModal.version.review_status]">{{ reviewMap[detailModal.version.review_status] }}</span></div>
            </div>
            <p v-if="detailModal.version.change_note" class="detail-note">变更说明：{{ detailModal.version.change_note }}</p>
            <p class="detail-search-hint">
              <span v-if="detailModal.version.searchable" class="published-badge">已进入默认检索</span>
              <span v-else class="offline-badge">旧版本 · 仅可查看，不进入默认检索</span>
            </p>
            <h4 class="detail-subtitle">文档内容</h4>
            <div v-if="detailModal.chunks.length" class="detail-content">
              <p v-for="c in detailModal.chunks" :key="c.index" class="chunk">{{ c.content }}</p>
            </div>
            <p v-else class="hint">该版本暂无解析内容</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { files } from '../api'
import { useToast } from '../composables/useToast'

const toast = useToast()
const list = ref([])
const filter = reactive({ bucket: '', status: '' })
const uploading = ref(false)
const uploadPercent = ref(0)
const page = ref(1)
const pageSize = 10
const fileInput = ref(null)
const pendingFiles = ref([])
const uploadForm = reactive({ docKey: '', changeNote: '' })
const versionModal = reactive({ open: false, loading: false, group: null, versions: [] })
const detailModal = reactive({ open: false, loading: false, version: null, chunks: [] })

const statusMap = { pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }
const reviewMap = { pending: '待审核', approved: '已通过', rejected: '已拒绝' }

const formatTime = (iso) => {
  if (!iso) return '-'
  const d = new Date(iso)
  return isNaN(d) ? iso : d.toLocaleString()
}

const totalPages = computed(() => Math.ceil(list.value.length / pageSize) || 1)
const pagedList = computed(() => {
  const start = (page.value - 1) * pageSize
  return list.value.slice(start, start + pageSize)
})

const goPage = (p) => {
  if (p >= 1 && p <= totalPages.value) page.value = p
}

const load = async (toastMsg = '') => {
  const params = {}
  if (filter.bucket) params.bucket = filter.bucket
  if (filter.status) params.status = filter.status
  try {
    const { data } = await files.list(params)
    const newList = data.files || []
    // 避免列表闪烁：只在数据真正变化时更新
    list.value = newList
    if (page.value > Math.ceil(newList.length / pageSize)) page.value = 1
    if (toastMsg) toast.success(toastMsg)
  } catch (err) {
    toast.error('加载文件列表失败')
  }
}

const onFilterChange = () => load('查询成功')
const onRefresh = () => load('刷新成功')

// 选择文件后进入上传设置阶段，允许填写文档标识与变更说明
const onFilesPicked = (e) => {
  pendingFiles.value = Array.from(e.target.files || [])
}

const cancelUpload = () => {
  pendingFiles.value = []
  uploadForm.docKey = ''
  uploadForm.changeNote = ''
  if (fileInput.value) fileInput.value.value = ''
}

const doUpload = async () => {
  if (!pendingFiles.value.length) return
  const fd = new FormData()
  for (const f of pendingFiles.value) fd.append('files', f)
  if (uploadForm.docKey) fd.append('doc_key', uploadForm.docKey)
  if (uploadForm.changeNote) fd.append('change_note', uploadForm.changeNote)
  uploading.value = true
  uploadPercent.value = 0
  try {
    const { data } = await files.upload(fd, (p) => { uploadPercent.value = p })
    toast.success('成功上传 ' + data.uploaded + ' 个文件')
    cancelUpload()
    setTimeout(load, 500)
  } catch (err) {
    toast.error('文件上传失败')
  } finally {
    uploading.value = false
  }
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
  } catch (err) {
    toast.error('加载版本历史失败')
  } finally {
    versionModal.loading = false
  }
}

const closeVersions = () => {
  versionModal.open = false
}

const openDetail = async (fileId) => {
  detailModal.open = true
  detailModal.loading = true
  detailModal.version = null
  detailModal.chunks = []
  try {
    const { data } = await files.versionDetail(fileId)
    detailModal.version = data.version
    detailModal.chunks = data.chunks || []
  } catch (err) {
    toast.error('加载版本详情失败')
  } finally {
    detailModal.loading = false
  }
}

const closeDetail = () => {
  detailModal.open = false
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; background: white; padding: 24px; border-radius: 12px; border: 1px solid #e2e8f0; }
h1 { font-size: 24px; color: #1e293b; }
p { color: #64748b; font-size: 14px; margin-top: 4px; }
.btn-upload { padding: 10px 20px; background: #6366f1; color: white; border-radius: 8px; cursor: pointer; font-size: 14px; }
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
.tag { background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status { padding: 4px 10px; border-radius: 12px; font-size: 12px; }
.status.pending { background: #f1f5f9; color: #64748b; }
.status.processing { background: #fef3c7; color: #92400e; }
.status.completed, .status.approved { background: #dcfce7; color: #166534; }
.status.failed, .status.rejected { background: #fee2e2; color: #991b1b; }
.empty { padding: 60px; text-align: center; color: #94a3b8; }
.mobile-cards { display: none; }
.file-card { padding: 16px; border-bottom: 1px solid #f1f5f9; }
.file-card-name { font-weight: 600; color: #1e293b; margin-bottom: 4px; word-break: break-all; }
.file-card-std { font-size: 13px; color: #64748b; margin-bottom: 8px; }
.file-card-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.pagination { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 16px; border-top: 1px solid #e2e8f0; }
.pagination button { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; background: white; cursor: pointer; font-size: 13px; }
.pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
.pagination button:not(:disabled):hover { background: #f8fafc; }
.page-info { font-size: 13px; color: #64748b; margin: 0 8px; }
@media (max-width: 768px) {
  .desktop-table { display: none; }
  .mobile-cards { display: block; }
  .page-header { flex-direction: column; gap: 12px; }
  .pagination { flex-wrap: wrap; }
}
.upload-form { padding: 24px; margin-bottom: 16px; }
.upload-form h3 { font-size: 16px; color: #1e293b; margin-bottom: 8px; }
.upload-form .hint { font-size: 13px; color: #64748b; margin-bottom: 16px; }
.form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.form-row label { width: 140px; font-size: 14px; color: #475569; }
.form-row input { flex: 1; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; }
.form-actions { display: flex; gap: 12px; margin-top: 8px; }
.btn-primary { padding: 10px 20px; background: #6366f1; color: white; border: none; border-radius: 8px; cursor: pointer; }
.btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }
.btn-cancel { padding: 10px 20px; background: #f1f5f9; color: #64748b; border: none; border-radius: 8px; cursor: pointer; }
.btn-link { background: none; border: none; color: #6366f1; cursor: pointer; font-size: 13px; padding: 0; }
.btn-link:hover { text-decoration: underline; }
.version-badge { display: inline-block; background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1100; display: flex; align-items: center; justify-content: center; padding: 16px; }
.modal { background: white; border-radius: 12px; width: 100%; max-width: 720px; max-height: 80vh; display: flex; flex-direction: column; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #e2e8f0; }
.modal-header h3 { font-size: 16px; color: #1e293b; }
.modal-close { background: none; border: none; font-size: 18px; cursor: pointer; color: #64748b; }
.modal-body { padding: 16px 24px; overflow: auto; }
.version-table { width: 100%; border-collapse: collapse; }
.version-table th { text-align: left; padding: 10px 12px; font-size: 12px; color: #64748b; border-bottom: 1px solid #e2e8f0; }
.version-table td { padding: 10px 12px; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
.version-table tr.published { background: #f0fdf4; }
.version-table .note { max-width: 180px; word-break: break-all; }
.published-badge { background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.offline-badge { background: #f1f5f9; color: #64748b; padding: 2px 8px; border-radius: 10px; font-size: 12px; }
.hint { color: #64748b; font-size: 14px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 24px; margin-bottom: 12px; }
.detail-grid > div { display: flex; flex-direction: column; gap: 4px; }
.detail-grid label { font-size: 12px; color: #94a3b8; }
.detail-grid span { font-size: 14px; color: #1e293b; }
.detail-note { font-size: 13px; color: #475569; margin-bottom: 8px; }
.detail-search-hint { margin-bottom: 12px; }
.detail-subtitle { font-size: 14px; color: #1e293b; margin: 12px 0 8px; padding-top: 12px; border-top: 1px solid #f1f5f9; }
.detail-content { max-height: 320px; overflow: auto; background: #f8fafc; border-radius: 8px; padding: 12px; }
.detail-content .chunk { font-size: 13px; color: #334155; line-height: 1.6; margin-bottom: 8px; white-space: pre-wrap; word-break: break-word; }
</style>
