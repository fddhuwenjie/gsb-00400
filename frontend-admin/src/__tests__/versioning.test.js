import { describe, it, expect, vi, beforeEach } from 'vitest'

// 通过 mock axios 实例，验证版本相关 API 客户端方法构造正确的请求
const mockGet = vi.fn(() => Promise.resolve({ data: {} }))
const mockPost = vi.fn(() => Promise.resolve({ data: {} }))

vi.mock('axios', () => ({
  default: {
    create: () => ({
      get: mockGet,
      post: mockPost,
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } }
    })
  }
}))

describe('Versioning API client', () => {
  let files
  beforeEach(async () => {
    mockGet.mockClear()
    mockPost.mockClear()
    const mod = await import('../api/index.js')
    files = mod.files
  })

  it('groups() 请求文档分组列表', async () => {
    await files.groups({ bucket: '方案' })
    expect(mockGet).toHaveBeenCalledWith('/files/groups', { params: { bucket: '方案' } })
  })

  it('versions() 请求指定分组的版本列表', async () => {
    await files.versions(42)
    expect(mockGet).toHaveBeenCalledWith('/files/groups/42/versions')
  })

  it('review() 携带 action 参数发起审核', async () => {
    await files.review(7, 'approve')
    expect(mockPost).toHaveBeenCalledWith('/files/7/review', null, { params: { action: 'approve' } })
  })

  it('list() 可请求全部版本', async () => {
    await files.list({ all_versions: true })
    expect(mockGet).toHaveBeenCalledWith('/files/list', { params: { all_versions: true } })
  })

  it('versionDetail() 请求指定版本详情', async () => {
    await files.versionDetail(15)
    expect(mockGet).toHaveBeenCalledWith('/files/versions/15')
  })
})
