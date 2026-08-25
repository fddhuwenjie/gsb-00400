import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  documents: { get: vi.fn(), list: vi.fn() },
  files: { get: vi.fn(), review: vi.fn(), upload: vi.fn(), list: vi.fn() }
}))

vi.mock('../api', () => ({
  documents: mocks.documents,
  files: mocks.files
}))

vi.mock('../composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() })
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: vi.fn() })
}))

import DocumentDetail from '../views/DocumentDetail.vue'
import Files from '../views/Files.vue'

const V1 = {
  file_id: 10, document_id: 1, version_number: 1, name: 'spec-v1.txt',
  standard_name: '标准名v1', bucket: '方案', status: 'completed',
  review_status: 'pending', is_published: false, uploaded_by: 'admin',
  upload_date: '2024-01-01T10:00:00', change_note: '初版', summary: 'v1摘要',
  review_comment: null, reviewed_at: null
}
const V2 = {
  file_id: 20, document_id: 1, version_number: 2, name: 'spec-v2.txt',
  standard_name: '标准名v2', bucket: '方案', status: 'completed',
  review_status: 'approved', is_published: true, uploaded_by: 'admin',
  upload_date: '2024-01-02T10:00:00', change_note: '更新架构', summary: 'v2摘要',
  review_comment: null, reviewed_at: '2024-01-02T11:00:00'
}
const DOC = {
  id: 1, doc_key: 'spec', title: 'spec-v2', bucket: '方案',
  current_version: 2, published_version: 2, published_file_id: 20,
  version_count: 2, has_pending: true, updated_at: '2024-01-02T10:00:00'
}

describe('DocumentDetail 文档版本详情页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.documents.get.mockResolvedValue({ data: { document: DOC, versions: [V2, V1] } })
    mocks.files.get.mockImplementation((id) =>
      Promise.resolve({ data: { file: id === 20 ? V2 : V1, tags: [], document: DOC, versions: [V2, V1] } })
    )
    mocks.files.review.mockResolvedValue({ data: { success: true } })
  })

  it('加载文档详情并展示版本历史，默认选中已发布版本', async () => {
    const wrapper = mount(DocumentDetail, { global: { mocks: { $router: { push: vi.fn() } } } })
    await flushPromises()

    expect(mocks.documents.get).toHaveBeenCalledWith('1')
    expect(mocks.files.get).toHaveBeenCalledWith(20) // 已发布版本优先
    const items = wrapper.findAll('.version-item')
    expect(items).toHaveLength(2)
    expect(wrapper.text()).toContain('v2')
    expect(wrapper.text()).toContain('v1')
    expect(wrapper.text()).toContain('更新架构') // 变更说明
  })

  it('可以切换到待审核版本并看到审核操作区', async () => {
    const wrapper = mount(DocumentDetail, { global: { mocks: { $router: { push: vi.fn() } } } })
    await flushPromises()

    // v2 已发布：没有审核操作区
    expect(wrapper.find('.review-box').exists()).toBe(false)

    await wrapper.findAll('.version-item')[1].trigger('click')
    await flushPromises()
    expect(mocks.files.get).toHaveBeenCalledWith(10)
    expect(wrapper.find('.review-box').exists()).toBe(true) // v1 待审核
  })

  it('退回时未填写原因则不提交审核', async () => {
    const wrapper = mount(DocumentDetail, { global: { mocks: { $router: { push: vi.fn() } } } })
    await flushPromises()
    await wrapper.findAll('.version-item')[1].trigger('click')
    await flushPromises()

    await wrapper.find('.btn-reject').trigger('click')
    expect(mocks.files.review).not.toHaveBeenCalled()
  })

  it('填写审核意见后可通过/退回，并携带版本号与原因', async () => {
    const wrapper = mount(DocumentDetail, { global: { mocks: { $router: { push: vi.fn() } } } })
    await flushPromises()
    await wrapper.findAll('.version-item')[1].trigger('click')
    await flushPromises()

    await wrapper.find('.btn-approve').trigger('click')
    await flushPromises()
    expect(mocks.files.review).toHaveBeenCalledWith(10, 'approve', null)

    // 审核后页面重载并回到已发布版本，需重新切换到待审核版本再退回
    await wrapper.findAll('.version-item')[1].trigger('click')
    await flushPromises()
    await wrapper.find('textarea').setValue('内容缺失，请补充')
    await wrapper.find('.btn-reject').trigger('click')
    expect(mocks.files.review).toHaveBeenCalledWith(10, 'reject', '内容缺失，请补充')
  })
})

describe('Files 文档列表页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.documents.list.mockResolvedValue({ data: { documents: [DOC] } })
    mocks.files.upload.mockResolvedValue({ data: { files: [{ is_new_document: false }] } })
  })

  it('以文档维度展示最新版本与已发布版本', async () => {
    const wrapper = mount(Files, { global: { mocks: { $router: { push: vi.fn() } } } })
    await flushPromises()

    const rows = wrapper.findAll('.doc-row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('spec-v2')
    expect(rows[0].text()).toContain('待审核')
    expect(wrapper.text()).toContain('v2') // 最新版本
    expect(wrapper.text()).toContain('v2') // 已发布版本（当前数据两者同号）
  })

  it('上传时携带变更说明参数', async () => {
    const wrapper = mount(Files, { global: { mocks: { $router: { push: vi.fn() } } } })
    await flushPromises()

    await wrapper.find('.note-input').setValue('更新第三章')
    const input = wrapper.find('input[type="file"]').element
    Object.defineProperty(input, 'files', {
      value: [new File(['content'], 'spec-v3.txt', { type: 'text/plain' })],
      configurable: true
    })
    await wrapper.find('input[type="file"]').trigger('change')
    await flushPromises()

    expect(mocks.files.upload).toHaveBeenCalledTimes(1)
    const [, , extra] = mocks.files.upload.mock.calls[0]
    expect(extra).toEqual({ change_note: '更新第三章' })
  })
})
