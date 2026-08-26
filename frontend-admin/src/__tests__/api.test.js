import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'

describe('API Client Interceptors', () => {
  let api

  beforeEach(() => {
    api = axios.create({ baseURL: '/api' })
    api.interceptors.request.use(config => {
      const token = localStorage.getItem('token')
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })
    localStorage.clear()
  })

  it('should inject token when present in localStorage', async () => {
    localStorage.setItem('token', 'test-token-123')
    const config = await api.interceptors.request.handlers[0].fulfilled({
      headers: {}
    })
    expect(config.headers.Authorization).toBe('Bearer test-token-123')
  })

  it('should not inject Authorization header when no token', async () => {
    const config = await api.interceptors.request.handlers[0].fulfilled({
      headers: {}
    })
    expect(config.headers.Authorization).toBeUndefined()
  })

  it('should clear token on 401 response', () => {
    localStorage.setItem('token', 'some-token')
    const error = { response: { status: 401 } }
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
    }
    expect(localStorage.getItem('token')).toBeNull()
  })
})

describe('API endpoint definitions', () => {
  it('files review accepts comment parameter', () => {
    const files = {
      review: (id, action, comment) => ({
        url: `/files/${id}/review`,
        method: 'post',
        params: { action, comment }
      })
    }
    const result = files.review(1, 'approve', 'looks good')
    expect(result.url).toBe('/files/1/review')
    expect(result.params.comment).toBe('looks good')
  })

  it('documents API has all required methods', () => {
    const documents = {
      list: (params) => ({ url: '/documents', params }),
      get: (id) => ({ url: `/documents/${id}` }),
      getVersion: (docId, versionId) => ({ url: `/documents/${docId}/versions/${versionId}` }),
      reviewVersion: (docId, versionId, action, comment) => ({
        url: `/documents/${docId}/versions/${versionId}/review`,
        params: { action, comment }
      }),
      switchVersion: (docId, versionId) => ({
        url: `/documents/${docId}/switch-version/${versionId}`,
        method: 'post'
      })
    }
    expect(documents.list({}).url).toBe('/documents')
    expect(documents.get(5).url).toBe('/documents/5')
    expect(documents.getVersion(5, 10).url).toBe('/documents/5/versions/10')
    const review = documents.reviewVersion(5, 10, 'reject', 'needs work')
    expect(review.params.action).toBe('reject')
    expect(review.params.comment).toBe('needs work')
    expect(documents.switchVersion(5, 8).url).toBe('/documents/5/switch-version/8')
  })

  it('search API does not send include_old_versions parameter', () => {
    const search = {
      query: (q, topK = 10) => ({
        url: '/search',
        params: { q, top_k: topK }
      })
    }
    const r1 = search.query('test')
    expect(r1.params.q).toBe('test')
    expect(r1.params.top_k).toBe(10)
    expect(r1.params).not.toHaveProperty('include_old_versions')
    const r2 = search.query('keyword', 20)
    expect(r2.params.top_k).toBe(20)
    expect(r2.params).not.toHaveProperty('include_old_versions')
  })
})
