import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(() => Promise.resolve({ data: {} })),
  post: vi.fn(() => Promise.resolve({ data: {} })),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() }
  }
}

vi.mock('axios', () => ({
  default: { create: () => mockApi }
}))

const { docs, files } = await import('../api')

describe('Docs/Versions API', () => {
  beforeEach(() => {
    mockApi.get.mockClear()
    mockApi.post.mockClear()
  })

  it('groups() 请求 GET /docs', async () => {
    await docs.groups()
    expect(mockApi.get).toHaveBeenCalledWith('/docs')
  })

  it('versions() 对文档标识进行 URL 编码', async () => {
    await docs.versions('产品A 方案')
    expect(mockApi.get).toHaveBeenCalledWith(`/docs/${encodeURIComponent('产品A 方案')}/versions`)
  })

  it('versionDetail() 请求版本详情', async () => {
    await docs.versionDetail(7)
    expect(mockApi.get).toHaveBeenCalledWith('/versions/7')
  })

  it('reviewVersion() 通过时不带退回原因', async () => {
    await docs.reviewVersion(7, 'approve')
    expect(mockApi.post).toHaveBeenCalledWith('/versions/7/review', null, { params: { action: 'approve' } })
  })

  it('reviewVersion() 退回时携带原因', async () => {
    await docs.reviewVersion(7, 'reject', '内容过期')
    expect(mockApi.post).toHaveBeenCalledWith('/versions/7/review', null, { params: { action: 'reject', note: '内容过期' } })
  })

  it('files.upload() 提交 FormData 到 /files/upload', async () => {
    const fd = new FormData()
    fd.append('doc_key', 'doc-A')
    fd.append('change_note', '初始版本')
    await files.upload(fd)
    expect(mockApi.post).toHaveBeenCalledWith('/files/upload', fd, expect.objectContaining({}))
  })
})

describe('Router', () => {
  it('包含版本管理路由 /versions', async () => {
    const { default: router } = await import('../router')
    expect(router.getRoutes().some(r => r.path === '/versions')).toBe(true)
  })
})
