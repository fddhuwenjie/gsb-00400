# 需求文档

## 简介

本文档定义了AI知识库管理系统的增强需求，涵盖交互反馈、响应式设计、视觉层次、安全性、依赖管理、API文档、测试用例、错误处理、Docker端口映射和数据卷配置共十个增强领域。目标是提升系统的用户体验、安全性、可维护性和部署便利性。

## 术语表

- **知识库系统（System）**: 由FastAPI后端、Vue3前端和Docker Compose部署组成的AI知识库管理系统
- **前端（Frontend）**: 基于Vue3 + Vite + 纯CSS构建的管理后台界面（frontend-admin）
- **后端（Backend）**: 基于FastAPI + SQLite + FAISS构建的API服务
- **通知组件（Toast_Component）**: 前端全局消息提示组件，用于显示操作成功/失败/警告信息
- **进度条组件（Progress_Component）**: 前端文件上传进度指示组件
- **Nginx反向代理（Nginx_Proxy）**: 前端容器中的nginx服务，负责静态文件服务和API请求转发
- **Docker_Compose**: 容器编排配置文件，定义后端和前端服务的部署方式
- **Swagger文档（Swagger_Docs）**: FastAPI内置的OpenAPI自动文档，通过/docs路径访问
- **环境变量配置（Env_Config）**: 通过.env文件和环境变量管理敏感信息的机制

## 需求

### 需求1：交互反馈机制

**用户故事：** 作为系统管理员，我希望在执行操作时获得清晰的反馈提示，以便了解操作的执行状态和结果。

#### 验收标准

1. WHEN 用户上传文件时，THE Progress_Component SHALL 显示每个文件的上传百分比进度
2. WHEN 文件上传成功完成时，THE Toast_Component SHALL 显示包含上传文件数量的成功提示消息
3. IF 文件上传失败，THEN THE Toast_Component SHALL 显示包含失败原因的错误提示消息
4. WHEN 用户执行审核、重建索引或处理待处理文件等操作时，THE Toast_Component SHALL 在操作完成后显示对应的成功或失败提示
5. THE Toast_Component SHALL 在显示3秒后自动消失
6. WHEN 多条提示同时存在时，THE Toast_Component SHALL 以堆叠方式从顶部依次排列显示

### 需求2：响应式设计

**用户故事：** 作为系统管理员，我希望在不同设备（桌面、平板、手机）上都能正常使用系统，以便在移动场景下也能管理知识库。

#### 验收标准

1. WHEN 视口宽度小于768px时，THE Frontend SHALL 将侧边栏折叠为可切换的汉堡菜单
2. WHEN 视口宽度小于768px时，THE Frontend SHALL 将文件列表表格转换为卡片式布局
3. WHEN 视口宽度在768px到1024px之间时，THE Frontend SHALL 将侧边栏收窄为仅显示图标的模式
4. THE Frontend SHALL 确保所有页面元素在320px到1920px视口宽度范围内无水平滚动条
5. WHEN 用户在移动设备上点击汉堡菜单图标时，THE Frontend SHALL 显示侧边栏覆盖层，并在点击覆盖层外部区域时关闭

### 需求3：视觉层次增强

**用户故事：** 作为系统管理员，我希望界面具有清晰的视觉层次，以便快速区分不同功能区域并提高操作效率。

#### 验收标准

1. THE Frontend SHALL 使用不同的背景色区分页面头部区域、筛选区域和内容区域
2. THE Frontend SHALL 在不同功能区域之间使用分隔线或间距进行视觉分隔
3. THE Frontend SHALL 为数据总览页面的统计卡片添加左侧彩色边框以区分不同指标类别
4. THE Frontend SHALL 为文件管理页面的操作按钮区域提供独立的视觉容器

### 需求4：安全性增强

**用户故事：** 作为系统部署人员，我希望敏感信息通过环境变量配置而非硬编码，以便在不同环境中安全部署系统。

#### 验收标准

1. THE Env_Config SHALL 通过环境变量读取SECRET_KEY，不在代码中包含默认的生产密钥值
2. WHEN SECRET_KEY环境变量未设置时，THE Backend SHALL 在启动时记录警告日志并使用随机生成的临时密钥
3. THE Docker_Compose SHALL 通过env_file指令引用.env文件来传递敏感环境变量
4. THE 知识库系统 SHALL 在代码仓库中提供.env.example文件，列出所有需要配置的环境变量及其说明
5. THE .gitignore SHALL 包含.env文件以防止敏感信息被提交到版本控制

### 需求5：依赖管理完善

**用户故事：** 作为开发人员，我希望项目的依赖版本有清晰的说明和分组，以便理解各依赖的用途并进行维护。

#### 验收标准

1. THE Backend SHALL 在requirements.txt中按功能分组组织依赖项，每组使用注释标明用途
2. THE Frontend SHALL 在package.json中为所有依赖项指定精确的版本号（使用固定版本而非范围）
3. THE 知识库系统 SHALL 在README.md中包含依赖版本兼容性说明章节

### 需求6：API文档

**用户故事：** 作为开发人员，我希望能通过浏览器访问自动生成的API文档，以便了解和调试后端接口。

#### 验收标准

1. THE Nginx_Proxy SHALL 将/api/docs路径的请求转发到后端的Swagger文档页面
2. THE Nginx_Proxy SHALL 将/api/redoc路径的请求转发到后端的ReDoc文档页面
3. THE Backend SHALL 为每个API端点提供中文描述的summary和description字段
4. THE Backend SHALL 为每个API端点定义明确的response_model或responses参数，描述返回数据结构

### 需求7：测试用例

**用户故事：** 作为开发人员，我希望项目包含完整的测试用例，以便在修改代码后验证功能的正确性。

#### 验收标准

1. THE Backend SHALL 包含针对认证模块（登录、令牌生成、令牌验证）的单元测试
2. THE Backend SHALL 包含针对文件上传和列表查询API的集成测试
3. THE Backend SHALL 包含针对搜索API的集成测试，验证仅返回已审核通过的文件
4. THE Backend SHALL 包含针对标签生成器的单元测试，验证标签生成和标准名称生成逻辑
5. THE Frontend SHALL 包含针对API客户端拦截器（token注入）的单元测试
6. THE Backend SHALL 使用pytest作为测试框架，测试配置文件位于backend/目录下

### 需求8：错误处理机制完善

**用户故事：** 作为系统管理员，我希望系统在出错时提供友好的错误提示和详细的错误日志，以便快速定位和解决问题。

#### 验收标准

1. THE Backend SHALL 注册全局异常处理器，将未捕获的异常转换为包含错误码和中文描述的JSON响应
2. THE Backend SHALL 将所有错误日志写入结构化日志文件（JSON格式），包含时间戳、错误级别、请求路径和错误详情
3. WHEN 后端API返回错误响应时，THE Frontend SHALL 通过Toast_Component显示用户友好的中文错误提示，而非原始错误信息
4. IF 前端收到401未授权响应，THEN THE Frontend SHALL 自动跳转到登录页面并显示"登录已过期，请重新登录"提示
5. THE Frontend SHALL 在API客户端中注册响应拦截器，统一处理所有API错误响应

### 需求9：Docker后端端口映射

**用户故事：** 作为系统部署人员，我希望能直接访问后端API端口，以便进行调试和外部系统集成。

#### 验收标准

1. THE Docker_Compose SHALL 为后端服务添加端口映射，将容器内8000端口映射到宿主机的指定端口
2. THE Docker_Compose SHALL 使用环境变量配置后端映射端口号，默认值为8000
3. THE 知识库系统 SHALL 在README.md中说明后端端口映射的用途和访问方式

### 需求10：数据卷配置完善

**用户故事：** 作为系统部署人员，我希望了解数据卷的目录结构和数据管理策略，以便正确备份和维护系统数据。

#### 验收标准

1. THE Docker_Compose SHALL 为数据卷定义明确的挂载路径，将kb-data卷挂载到容器内的/data目录
2. THE Docker_Compose SHALL 为上传文件目录和向量数据库目录分别配置独立的卷或子路径
3. THE 知识库系统 SHALL 在README.md中包含数据卷目录结构说明，列出/data下各子目录的用途
4. THE 知识库系统 SHALL 在README.md中包含数据备份和恢复的操作指南
