# 换电脑继续开发

这份说明对着 2026-11-20 这台开发机写的。仓库是私有的：

https://github.com/xxyGoTop/ai-toy-studio

GitHub 上目前的最新提交还是早期骨架（`1f2faa9`）。侧边栏、GLTF 配套上传、按颜色拆分、彩色 3MF、右侧只留打印，都还在这台电脑的工作区里，没有提交。

换电脑之前二选一：

1. 把整个 `E:\work_agent\ai-toy-studio` 拷走。`.venv` 和 `apps\web\node_modules` 可以不拷，到新电脑重装。
2. 在这台电脑先提交并推送，新电脑再 `git clone`。不推送的话，新电脑拉下来的是旧骨架。

下面这些不会进 Git，新电脑上要重新准备：

- `.env`（有本机软件路径，不要提交）
- `.venv`、`node_modules`
- `storage\toy_studio.db` 和已经导入的模型。新电脑打开是空项目。

## 现在的使用流程

界面只保留上传。文字生成模型的入口已经藏起来，后端的 Meshy / Tripo 适配器还在，密钥仍是占位符。

```text
新建页面
  → 上传 STL / OBJ / GLB，或 GLTF 连同 .bin、贴图
  → 视口里查看（GLB/GLTF 保留原色，STL 是单色）
  → 需要的话按颜色拆分，生成一块平铺开的预览
  → 打印页「导出并打开切片」
       用组装好的模型按颜色分成最多 4 份
       写成 Bambu 3MF，颜色写进 4 个料槽
       打开 Bambu Studio
  → 在 Bambu Studio 里自己切片、自己发送到 A1
```

「导出并打开切片」不会切片，也不会发给打印机。左下角单独的导出图标仍然只出 STL，STL 没有颜色。

拆分出来的模型是平铺预览。打印时如果当前选中的是拆分结果，后端会改用它的父模型，这样零件还在原来的位置上。父记录如果已经被删掉，就会退回用这份平铺模型，打出来是散开的。

## 彩色 3MF 方案

打印机按 Bambu Lab A1 + AMS Lite 设计，最多 4 个料槽。颜色多于 4 种时，按面数加权，把最近的颜色合并进 4 个槽，并在页面上告诉用户合并了哪些。

预设固定为：

- 机器：`Bambu Lab A1 0.4 nozzle`
- 工艺：`0.20mm Standard @BBL A1`
- 耗材：`Bambu PLA Basic @BBL A1`

实现分三步：

1. `blender/scripts/export_color_stls.py` 按材质颜色分组，去掉地面，每个颜色写一个 STL。GLB/GLTF 先按米转毫米（×1000）。换算后最大边超过约 220 mm，就缩到 200 mm，再放到 A1 热床中心（128, 128），底面贴在 z = 0。STL/OBJ 按毫米，不再乘 1000。
2. 调用 `bambu-studio.exe` 的命令行，带上官方预设，`--arrange 0`，导出 3MF。官方预设文件里没有 `filament_colour`，所以这一步只负责得到一份完整的 A1 工程。
3. `backend/app/services/bambu_color.py` 改这个 3MF：写入 4 个料槽颜色，把每个零件的挤出机设成对应槽位，并把「落到热床上」的那层位移清掉，避免四个零件被压到同一高度。

接口是 `POST /api/v1/models/{id}/open-colored`。前端这次请求的超时是 300 秒。

## 要装的软件

| 软件 | 这台电脑的版本 | 下载 |
|------|----------------|------|
| Git | 已装 | https://git-scm.com/download/win |
| Python | 3.12.4 | https://www.python.org/downloads/windows/ 选 3.12 |
| Node.js | 20.19.0 | https://nodejs.org/ 选 20 LTS |
| Blender | 5.3.0（2026-11-10） | https://www.blender.org/download/ |
| Bambu Studio | 02.09.01.70 | https://bambulab.com/zh/download/studio 或 https://github.com/bambulab/BambuStudio/releases |

这台电脑上的实际路径：

- Blender：`D:\blander5.3\blender.exe`。目录名是 `blander`，不是 `blender`。
- Bambu Studio：`D:\BambuStudio\bambu-studio.exe`。安装包是 `Bambu_Studio_win-v02.09.01.70`，解压后可执行文件就在这个目录，不是再套一层子目录。
- 预设：`D:\BambuStudio\resources\profiles\BBL\`

新电脑路径可以不同，但要同时改两个地方：

- `.env` 里的 `BLENDER_EXECUTABLE` 和 `BAMBU_STUDIO_EXECUTABLE`
- `backend/app/services/bambu_color.py` 和 `backend/app/services/bambu_preset.py` 里写死的 `D:\BambuStudio\resources\profiles\BBL`

只改 `.env` 时，软件能被打开，彩色 3MF 仍会去旧盘找预设。

这台电脑访问外网时用了本机代理 `http://127.0.0.1:1080`。新电脑能直接打开 GitHub 和 npm 就不要设置 `HTTP_PROXY`。

## 新电脑第一次启动

```powershell
cd E:\work_agent\ai-toy-studio
git clone https://github.com/xxyGoTop/ai-toy-studio.git .
copy .env.example .env
```

编辑 `.env`：把 Blender 和 Bambu Studio 的路径改成新电脑上的路径。`MESHY_API_KEY`、`TRIPO_API_KEY` 保持占位即可，当前界面不用它们。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

cd apps\web
npm install
```

后端：

```powershell
cd E:\work_agent\ai-toy-studio
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

前端另开一个窗口：

```powershell
cd E:\work_agent\ai-toy-studio\apps\web
npm run dev
```

浏览器打开 http://127.0.0.1:5173 。前端把 `/api` 和 `/storage` 代理到 http://127.0.0.1:8000 。

确认 Blender 能在后台跑：

```powershell
& "D:\blander5.3\blender.exe" -b --version
```

把路径换成新电脑的 Blender。能打印 `Blender 5.3.0` 就可以。

## 改代码之后怎么生效

- 改 `apps\web`：Vite 会自己刷新。
- 改 `blender\scripts`：下次调用时从磁盘读，不用重启后端。
- 改 `backend`：现在的启动命令没有热重载。先结束占用 8000 端口的进程，再按上面的命令重新启动。`get_settings()` 有缓存，只改 `.env` 也要重启。

端口被占时会报 `Errno 10048`。先查是谁在听 8000，再结束它：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
Stop-Process -Id <进程号> -Force
```

## 遇到过的坑

**GLTF 只传了 json。** 外部 buffer 还是原来的文件名，例如 `firetruck_anim_full.bin`。只保存 json、又把文件名改掉，加载就会报 `Failed to load buffer`。上传要连同 `.bin`、`.png`、`.jpg`、`.jpeg`、`.webp` 一起选。后端把它们放在同一个目录，并把 GLTF 里的地址改成文件名。缺文件时接口直接返回 400，并写明缺哪一个。

**视口把车身藏掉了。** 以前会把比中位尺寸大 8 倍的网格，以及细长零件当成异常件隐藏。消防车的车身、吊臂、车架都中招，看起来像水炮浮在空中。现在只隐藏真正的地面：名字里有地面、ground、floor、影棚，或者又大又扁的背景板。细长零件要留着。

**拆分结果是空的。** Blender 的 `bmesh` 在 `index_update()` 之前，`vert.index` 是 -1。顶点被收成一个点，面建不出来，接口报「拆分后没有零件」。合并零件前必须先 `index_update()`。

**拆分预览不能直接拿去打印。** 拆分 GLB 是故意平铺的。打印要回到组装好的父模型。父模型记录被删除后，当前代码会停在这份平铺文件上。

**STL 带不了颜色。** Bambu 打开 STL 只有一个耗材。多色要 3MF：`filament_colour` 是英式拼写，官方预设 json 里没有这个字段，它只存在于保存出来的工程里。`Metadata` 里的 Application 必须是 `BambuStudio-` 加安装版本，否则工程配置会被忽略。A1 是单喷嘴，`flush_volumes_matrix` 必须是颜色数的平方，对角线为 0；`flush_volumes_vector` 是颜色数的 2 倍；`inherits_group` 是颜色数加 2。长度不对时文件能打开，切片会报 `Flush volumes matrix do not match`。

**打开 3MF 提示没有几何数据。** 重新打包 zip 会破坏 Bambu Studio 的加载：PNG 缩略图必须无压缩存储，条目顺序不能变，每个条目的压缩方式要保留。Python `zipfile` 新建 `ZipInfo` 会丢掉这些。正确做法是复用原始 `ZipInfo` 对象，只替换 `Metadata/project_settings.config` 里的 `filament_colour`，不动 `3D/3dmodel.model` 和 `Metadata/model_settings.config`。挤出机编号由命令行 `--load-filament-ids` 写好，不用再改。不要加 `--ensure-on-bed`。

**单位。** glTF 规范是米。消防车大约 12 个单位，当成米就是 12 米。不乘 1000 会小到看不见；乘完不限制尺寸又会远超 A1 的 256 mm 热床。

**Bambu 命令行和图形界面可以同时在。** 这台机器上 GUI 已经开着时，`--export-3mf` 仍然能写出文件。第一次打开图形界面可能有向导，需要在那台电脑上点过去。

**删除不要用 `window.confirm`。** 在当前这个内置浏览器里它会直接返回取消，删除按钮看起来没反应。页面和模型的删除是直接执行的。

**Blender 5.3 的材质节点。** `material.use_nodes` 会给弃用警告，5.3 里还能用。Blender 6 会去掉它，到时候 `color_of()` 要改。

**后端日志里的退出码 `4294967295`。** 在 Windows 上这通常是进程被主动结束后的退出码，不一定是服务崩溃。看到它时先看 8000 端口上还有没有新的 uvicorn。

**PowerShell 传 Python 代码。** 引号套引号很容易把 SQL 或路径截断。要查数据库时写成临时 `.py` 再运行。
