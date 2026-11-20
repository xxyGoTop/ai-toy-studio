# Architecture

## Overview

AI 3D Toy Studio 采用本地 Monorepo：

- `apps/web`：Vue 3 创作工作台 + Three.js 预览
- `backend`：FastAPI 任务编排、文件管理、SQLite
- `blender/scripts`：Blender 独立进程自动化
- `providers`：Meshy / Tripo AI 适配器
- `storage`：按项目归档源文件、加工文件、导出文件

## Principles

1. 单机本地优先，不引入微服务。
2. Blender 通过子进程执行，不阻塞 API worker。
3. 源文件永不覆盖，加工结果生成新版本记录。
4. AI Key 仅存在于后端环境变量。
5. 检查报告区分 ERROR / WARNING / INFO。
6. ERROR 模型禁止进入导出打印主流程，除非人工确认策略另行放开。
7. 切片与打印第一版由 Bambu Studio 人工确认。

## Data flow

```text
Web UI
  -> FastAPI
      -> SQLite metadata
      -> storage/*
      -> Blender subprocess
      -> AI Provider (optional)
  <- model preview / check report / export path
```

## Target printer

Bambu Lab A1，设计时按可用打印空间留余量（建议模型占用不超过约 240mm）。
