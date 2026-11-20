# AI 3D Toy Studio

面向 Bambu Lab A1 的个人 AI 玩具设计与打印工作流。

支持三种创作入口：

1. **AI 原创生成**：文字 / 图片 → Meshy / Tripo → GLB
2. **现成模型二次创作**：导入 STL / OBJ / GLB，Blender 加工
3. **Blender 手工建模**：脚本化基础零件与装配

统一生产链路：

```text
创意输入 → 模型导入 → Blender 自动加工 → 网格检查 → 导出 STL/3MF → Bambu Studio → A1 打印
```

## 技术栈

| 模块 | 选型 |
|------|------|
| 前端 | Vue 3 + TypeScript + Three.js |
| 后端 | Python FastAPI + SQLite |
| 建模 | Blender 5.3 + Python API |
| AI | Meshy / Tripo Provider 适配器 |
| 切片 | Bambu Studio（半自动） |
| 打印机 | Bambu Lab A1 |

## 快速开始

项目路径：`E:\work_agent\ai-toy-studio`

### 1. 环境

- Windows
- Python 3.12+
- Node.js 20+
- Blender：默认 `D:\blander5.3\blender.exe`

### 2. 后端

```powershell
cd E:\work_agent\ai-toy-studio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

或直接：

```powershell
.\scripts\dev-backend.ps1
```

### 3. 前端

```powershell
cd apps\web
npm install
npm run dev
```

或：

```powershell
.\scripts\dev-web.ps1
```

浏览器打开：http://127.0.0.1:5173

### 4. Blender 冒烟测试

```powershell
& "D:\blander5.3\blender.exe" -b --python scripts\make_demo_stl.py -- storage\source\demo\toy_demo.stl
```

## 当前版本范围（V0.1–V0.3）

- [x] 项目管理（SQLite）
- [x] 模型导入与文件归档
- [x] Three.js 3D 预览
- [x] Blender 后台调用：导入 / 尺寸标准化 / 网格检查 / STL 导出
- [x] 检查报告 ERROR / WARNING / INFO
- [x] AI Provider 适配器骨架（Meshy / Tripo）
- [ ] V0.4 完整 AI 生成计费链路联调（需 API Key）
- [ ] V0.5 拆件与连接结构
- [ ] V0.6 Bambu Studio 深度集成

## 目录结构

```text
ai-toy-studio/
├── apps/web/          # Vue 创作工作台
├── backend/           # FastAPI
├── blender/scripts/   # Blender 自动化
├── providers/         # AI 3D Provider
├── storage/           # 本地模型与导出
└── docs/              # 架构与操作文档
```

## 安全原则

1. AI API Key 只放在后端 `.env`
2. 源文件永不覆盖，按版本归档
3. 未通过检查或未人工确认的模型不进入打印流程
4. 第一版切片与打印由 Bambu Studio 人工确认

## 文档

- [架构](docs/architecture.md)
- [API](docs/api.md)
- [Blender](docs/blender.md)
- [打印](docs/printing.md)
