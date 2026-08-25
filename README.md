# AI知识库整理系统

## How to Run

```bash
# 1. 复制环境变量配置文件
cp .env.example .env
# 编辑 .env 设置 SECRET_KEY 等参数

# 2. 构建并启动所有服务
docker-compose up --build -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

## Services

| 服务 | 端口 | 访问地址 | 说明 |
|------|------|----------|------|
| frontend-admin | 8181 | http://localhost:8181 | 管理后台 |
| API文档 | - | http://localhost:8181/api/docs | Swagger交互式文档 |
| API文档 | - | http://localhost:8181/api/redoc | ReDoc文档 |

## 测试账号

首次使用请在登录页点击"初始化管理员账号"按钮创建账号：

- 用户名: `admin`
- 密码: `admin123`

## 环境变量配置

复制 `.env.example` 为 `.env`，按需修改：

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| SECRET_KEY | 是 | 随机生成（不安全） | JWT签名密钥，生产环境必须设置 |
| DATABASE_URL | 否 | sqlite+aiosqlite:///./data/knowledge.db | 数据库连接地址 |
| BACKEND_PORT | 否 | 8000 | 后端API外部映射端口 |
| HF_ENDPOINT | 否 | https://hf-mirror.com | HuggingFace镜像地址（国内加速） |

> 未设置 SECRET_KEY 时系统会生成随机临时密钥，每次重启后token失效，仅适合开发环境。

## 端口映射

- 前端管理后台：宿主机 `8181` → 容器 `80`
- 后端API：宿主机 `${BACKEND_PORT:-8000}` → 容器 `8000`

修改后端端口示例：
```bash
# .env
BACKEND_PORT=9000
```

## 数据卷目录结构

所有持久化数据存储在 Docker volume `kb-data` 中，映射到容器 `/data` 目录：

```
/data/
├── knowledge.db      # SQLite数据库（文件元数据、用户信息）
├── uploads/           # 上传的原始文件
├── faiss_index/       # FAISS向量索引文件
├── models/            # AI模型缓存（SentenceTransformer等）
└── logs/              # 应用日志
    └── app.log        # 结构化JSON日志（自动轮转，最大10MB×5份）
```

## 数据备份与恢复

```bash
# 备份整个数据卷
docker run --rm -v kb-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/kb-data-backup.tar.gz /data

# 恢复数据卷
docker run --rm -v kb-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/kb-data-backup.tar.gz -C /

# 仅备份数据库
docker cp kb-backend:/data/knowledge.db ./knowledge.db.bak
```

## 依赖版本兼容性

### 后端关键依赖

| 依赖 | 版本 | 兼容性说明 |
|------|------|-----------|
| faiss-cpu | 1.7.4 | 需配合 numpy==1.24.3 |
| numpy | 1.24.3 | 1.25+ 与 faiss-cpu 1.7.4 不兼容 |
| bcrypt | 4.0.1 | 4.1+ 接口有变化，需使用 4.0.x |
| torch | 2.0.1 | sentence-transformers 2.2.2 兼容版本 |
| sentence-transformers | 2.2.2 | 需配合 transformers==4.30.2 |

### 前端关键依赖

所有前端依赖使用精确版本号（无 `^` 或 `~` 前缀），确保构建一致性。

| 依赖 | 版本 | 说明 |
|------|------|------|
| vue | 3.4.0 | 核心框架 |
| vite | 5.0.10 | 构建工具 |
| vitest | 1.2.0 | 测试框架 |

## 题目内容

### 系统功能

本系统实现本地化AI批量文件解析、自动分类、标签生成、知识关系建立，支持：

**Step 0-1: 文件入库**
- 批量上传文件到集中区
- 自动记录元数据（路径、类型、大小、日期）
- 支持断点续传和增量处理

**Step 2: 文件内容解析**
- 文档类（PDF/Word/PPT/TXT）：提取文本、标题、表格
- 视频类：Whisper语音转文字、时间轴索引（可选）
- 安装包/压缩包：提取元信息

**Step 3: 自动生成标准名 & 标签**
- 标准名规则：【产品】-【内容类型】-【用途/角色】-【版本】-【年份】
- 标签类型：基础标签、语义标签、状态标签、关系标签

**Step 4: 知识关系建立**
- 基于内容关键词自动建立文件关联
- 支持方案↔彩页、文档↔视频等关系

**Step 5: 人工审核确认**
- 人只做确认，不改名
- 支持接受/拒绝AI建议

**Step 6: 更新本地知识库**
- FAISS向量库支持语义检索
- 文件索引库（标准名+原路径+标签）

### 技术栈

- 后端: FastAPI + SQLite + FAISS
- 前端: Vue3 + 原生CSS（现代化设计）
- AI: SentenceTransformer + Tesseract OCR
- 视频: Whisper（可选安装）

### 测试文件

`test_files/` 目录包含各类型测试文件：
- 方案类：技术架构、解决方案
- 彩页类：产品宣传材料
- 安装包类：部署手册、安装说明
- 视频类：演示脚本、培训材料
