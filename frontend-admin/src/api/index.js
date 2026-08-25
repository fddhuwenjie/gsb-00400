import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// 请求拦截器：注入token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截器：统一错误处理
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export const auth = {
  login: (data) => api.post('/auth/login', new URLSearchParams(data)),
  init: () => api.post('/auth/init'),
  me: () => api.get('/auth/me')
}

export const files = {
  list: (params) => api.get('/files/list', { params }),
  get: (id) => api.get(`/files/${id}`),
  upload: (formData, onProgress) => api.post('/files/upload', formData, {
    onUploadProgress: onProgress ? (e) => onProgress(Math.round((e.loaded * 100) / e.total)) : undefined
  }),
  review: (id, action) => api.post(`/files/${id}/review`, null, { params: { action } }),
  reindex: () => api.post('/files/reindex'),
  processPending: () => api.post('/files/process-pending')
}

export const docs = {
  groups: () => api.get('/docs'),
  versions: (docKey) => api.get(`/docs/${encodeURIComponent(docKey)}/versions`),
  versionDetail: (versionId) => api.get(`/versions/${versionId}`),
  reviewVersion: (versionId, action, note) => api.post(`/versions/${versionId}/review`, null, { params: { action, ...(note ? { note } : {}) } })
}

export const search = {
  query: (q, topK = 10) => api.get('/search', { params: { q, top_k: topK } })
}

export const stats = {
  overview: () => api.get('/stats/overview'),
  tags: () => api.get('/stats/tags')
}
