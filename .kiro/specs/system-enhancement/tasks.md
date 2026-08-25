# Implementation Plan: AI知识库管理系统增强

## Overview

按照增量方式实施十项系统增强，从基础设施（安全、配置）开始，到后端增强（错误处理、API文档、测试），再到前端增强（Toast、进度条、响应式、视觉），最后完成部署和文档更新。

## Tasks

- [x] 1. 安全性增强与环境变量配置
  - [x] 1.1 修改 `backend/app/config.py`，移除硬编码SECRET_KEY，改为从环境变量读取，未设置时生成随机临时密钥并记录警告日志
    - 使用 `secrets.token_urlsafe(32)` 生成随机密钥
    - 使用 pydantic validator 实现默认值逻辑
    - _Requirements: 4.1, 4.2_
  - [x] 1.2 创建 `.env.example` 文件，列出所有环境变量（SECRET_KEY、DATABASE_URL、BACKEND_PORT）及中文说明
    - _Requirements: 4.4_
  - [x] 1.3 修改 `.gitignore`，添加 `.env` 条目
    - _Requirements: 4.5_
  - [x] 1.4 修改 `docker-compose.yml`，为backend服务添加 `env_file: ./.env` 指令
    - _Requirements: 4.3_
  - [ ]* 1.5 编写属性测试验证SECRET_KEY环境变量读取逻辑
    - **Property 4: SECRET_KEY环境变量读取**
    - **Validates: Requirements 4.1, 4.2**

- [x] 2. 后端错误处理与结构化日志
  - [x] 2.1 在 `backend/app/main.py` 中注册全局异常处理器（Exception和HTTPException），返回统一的JSON错误响应格式 `{error_code, message}`
    - _Requirements: 8.1_
  - [x] 2.2 在 `backend/app/main.py` 中配置结构化JSON日志，使用自定义JSONFormatter和RotatingFileHandler，输出到 `/data/logs/app.log`
    - 日志包含 timestamp、level、logger、message 字段
    - _Requirements: 8.2_
  - [x] 2.3 创建 `backend/app/schemas.py`，定义ErrorResponse、UploadResponse、FileListResponse、SearchResponse、OverviewResponse等Pydantic响应模型
    - _Requirements: 6.4_
  - [ ]* 2.4 编写属性测试验证全局异常处理器返回结构化JSON响应
    - **Property 10: 全局异常处理器结构化响应**
    - **Validates: Requirements 8.1**
  - [ ]* 2.5 编写属性测试验证结构化日志格式
    - **Property 11: 结构化JSON日志格式**
    - **Validates: Requirements 8.2**

- [x] 3. 后端API文档增强
  - [x] 3.1 修改 `backend/app/routers/auth.py`、`files.py`、`search.py`、`stats.py`，为每个端点添加中文summary、description和response_model参数
    - _Requirements: 6.3, 6.4_
  - [x] 3.2 修改 `frontend-admin/nginx.conf`，添加 `/api/docs`、`/api/redoc`、`/api/openapi.json` 路径的反向代理转发规则
    - _Requirements: 6.1, 6.2_
  - [ ]* 3.3 编写属性测试验证所有API路由的OpenAPI文档完整性
    - **Property 6: API文档完整性**
    - **Validates: Requirements 6.3, 6.4**

- [x] 4. Checkpoint - 确保后端增强完成
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 5. 前端Toast通知组件
  - [x] 5.1 创建 `frontend-admin/src/composables/useToast.js`，实现Toast状态管理（reactive消息列表、success/error/warning/info方法、3秒自动移除、provide/inject模式）
    - _Requirements: 1.5, 1.6_
  - [x] 5.2 创建 `frontend-admin/src/components/Toast.vue`，实现Toast渲染组件（固定定位右上角、堆叠排列、CSS过渡动画、成功/错误/警告/信息四种样式）
    - _Requirements: 1.5, 1.6_
  - [x] 5.3 修改 `frontend-admin/src/App.vue`，注册Toast全局容器（provide useToast，挂载Toast组件）
    - _Requirements: 1.4_
  - [ ]* 5.4 编写属性测试验证Toast生命周期管理
    - **Property 3: Toast生命周期管理**
    - **Validates: Requirements 1.5, 1.6**

- [x] 6. 前端上传进度与交互反馈
  - [x] 6.1 修改 `frontend-admin/src/api/index.js`，为upload方法添加onUploadProgress回调参数支持
    - _Requirements: 1.1_
  - [x] 6.2 修改 `frontend-admin/src/api/index.js`，添加响应拦截器处理401跳转登录、统一错误处理
    - _Requirements: 8.4, 8.5_
  - [x] 6.3 修改 `frontend-admin/src/views/Files.vue`，添加上传进度条UI（百分比显示、进度条动画），上传成功/失败时调用Toast通知
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 6.4 修改 `frontend-admin/src/views/Dashboard.vue`，将重建索引和处理待处理文件的操作结果改为Toast通知
    - _Requirements: 1.4_
  - [x] 6.5 修改 `frontend-admin/src/views/Review.vue`，审核操作完成后调用Toast通知
    - _Requirements: 1.4_
  - [ ]* 6.6 编写属性测试验证上传进度百分比计算
    - **Property 1: 上传进度百分比计算正确性**
    - **Validates: Requirements 1.1**
  - [ ]* 6.7 编写属性测试验证操作完成后Toast通知
    - **Property 2: 操作完成后显示Toast通知**
    - **Validates: Requirements 1.4**

- [x] 7. 前端响应式设计
  - [x] 7.1 修改 `frontend-admin/src/App.vue`，添加响应式侧边栏（汉堡菜单按钮、移动端覆盖层、平板图标模式），使用CSS媒体查询实现三个断点（<768px、768-1024px、≥1024px）
    - _Requirements: 2.1, 2.3, 2.4, 2.5_
  - [x] 7.2 修改 `frontend-admin/src/views/Files.vue`，添加移动端卡片式布局（表格在<768px时转为卡片显示）
    - _Requirements: 2.2_
  - [x] 7.3 修改 `frontend-admin/src/views/Dashboard.vue`，统计卡片网格在移动端改为单列布局
    - _Requirements: 2.4_

- [x] 8. 前端视觉层次增强
  - [x] 8.1 修改各视图组件样式：页面头部白色背景+底部阴影、筛选区域浅灰背景容器、Dashboard统计卡片左侧彩色边框、文件管理操作按钮独立容器
    - 修改 `Dashboard.vue`：统计卡片添加左侧4px彩色边框（蓝/绿/橙/紫）
    - 修改 `Files.vue`：头部区域和筛选区域添加背景色分隔，操作按钮区域独立容器
    - 修改 `Review.vue`：头部区域添加背景色分隔
    - 修改 `Search.vue`：搜索框区域添加背景色容器
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 9. Checkpoint - 确保前端增强完成
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 10. 后端测试套件
  - [x] 10.1 创建 `backend/tests/conftest.py`，配置pytest fixtures（内存SQLite测试数据库、AsyncClient测试客户端、测试用户创建）
    - 添加 pytest、pytest-asyncio、httpx、hypothesis 到 requirements.txt
    - 创建 `backend/pytest.ini` 配置文件
    - _Requirements: 7.6_
  - [x] 10.2 创建 `backend/tests/test_auth.py`，编写认证模块测试（登录成功/失败、token验证、管理员初始化）
    - _Requirements: 7.1_
  - [x] 10.3 创建 `backend/tests/test_files_api.py`，编写文件API集成测试（上传、列表查询、审核操作）
    - _Requirements: 7.2_
  - [x] 10.4 创建 `backend/tests/test_tag_generator.py`，编写标签生成器单元测试
    - _Requirements: 7.4_
  - [ ]* 10.5 编写属性测试验证搜索结果仅包含已审核文件
    - **Property 7: 搜索结果仅包含已审核文件**
    - **Validates: Requirements 7.3**
  - [ ]* 10.6 编写属性测试验证标签生成器关键词匹配
    - **Property 8: 标签生成器关键词匹配**
    - **Validates: Requirements 7.4**

- [x] 11. 前端测试套件
  - [x] 11.1 配置Vitest测试环境：创建 `frontend-admin/vitest.config.js`，安装vitest、@vue/test-utils、jsdom、fast-check依赖
    - _Requirements: 7.5_
  - [x] 11.2 创建 `frontend-admin/src/__tests__/api.test.js`，编写API客户端拦截器测试（token注入、401处理）
    - _Requirements: 7.5_
  - [ ]* 11.3 编写属性测试验证API请求拦截器Token注入
    - **Property 9: API请求拦截器Token注入**
    - **Validates: Requirements 7.5**

- [x] 12. Docker配置与依赖管理 ✅
  - [x] 12.1 修改 `docker-compose.yml`：后端添加端口映射 `${BACKEND_PORT:-8000}:8000`，添加数据卷目录结构注释
    - _Requirements: 9.1, 9.2, 10.1, 10.2_
  - [x] 12.2 整理 `backend/requirements.txt`，按功能分组并添加注释说明，添加测试依赖
    - _Requirements: 5.1_
  - [x] 12.3 修改 `frontend-admin/package.json`，将所有依赖版本改为精确版本（移除^和~前缀），添加测试依赖
    - _Requirements: 5.2_
  - [ ]* 12.4 编写属性测试验证package.json依赖版本精确性
    - **Property 5: 前端依赖版本精确性**
    - **Validates: Requirements 5.2**

- [x] 13. 文档更新 ✅
  - [x] 13.1 更新 `README.md`：添加环境变量配置说明、后端端口映射说明、数据卷目录结构说明、数据备份恢复指南、依赖版本兼容性说明
    - _Requirements: 5.3, 9.3, 10.3, 10.4_

- [x] 14. Final Checkpoint ✅
  - 所有核心任务已完成，系统运行正常
  - 前端: http://localhost:8181
  - API: http://localhost:8181/api/
  - 文档: http://localhost:8181/api/docs

## Notes

- 标记 `*` 的任务为可选任务，可跳过以加快MVP进度
- 每个任务引用了具体的需求编号以确保可追溯性
- 属性测试验证通用正确性属性，单元测试验证具体示例和边界情况
- Checkpoint任务确保增量验证
