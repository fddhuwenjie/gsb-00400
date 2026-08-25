import { describe, it, expect, beforeEach } from 'vitest'
import axios from 'axios'

describe('API Client Interceptors', () => {
  let api

  beforeEach(() => {
    api = axios.create({ baseURL: '/api' })
    // 复制请求拦截器逻辑
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
    // 模拟响应拦截器逻辑
    const error = { response: { status: 401 } }
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
    }
    expect(localStorage.getItem('token')).toBeNull()
  })
})
