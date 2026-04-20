# Shenzhen Weather Video Downloader

一个用于下载深圳市气象局“实景监测”页面视频的 Python 脚本。

和旧版通过时间规律手工拼接视频文件名的方式不同，这个版本直接读取页面实际使用的数据源 `rt_list.js`，自动发现当前可用观测点及其最新视频地址，再执行下载或持续监控。

适合的使用场景：
- 一次性抓取当前所有可用观测点的视频
- 只抓取某几个站点或某类站点（例如“福田”“西涌”）
- 长时间运行，自动发现并下载新视频

## 功能特性

- 自动读取当前可用观测点列表
- 支持按观测点名称关键词过滤
- 支持按观测点 code 过滤
- 支持一次性下载当前视频
- 支持 `watch` 模式持续轮询并下载新视频
- 下载时使用 `.part` 临时文件，完成后原子替换
- 自动跳过已存在且大小正常的文件
- 按“视频文件名中的日期”归档，而不是按下载当天归档
- 每轮执行生成 `summary-*.json` 摘要文件
- 保存长期状态到 `state/state.json`
- 控制台 + 文件日志
- 网络请求自动重试

## 工作原理

页面前端会从以下接口读取当前可用站点：

```text
https://weather.121.com.cn/data_cache/video/rt/rt_list.js
```

返回内容中包含：
- 观测点 code
- 观测点 name
- 当前最新视频相对路径 `mp4`
- 经纬度、高度、地址等信息

脚本直接读取这些数据，而不是再按旧逻辑手动拼接时间和文件名，因此它能更好地适应：
- 观测点上下线变化
- 页面缓存策略变化
- 各站点视频刷新节奏不一致

## 运行环境

- Python 3.9+
- requests

安装依赖：

```bash
pip install -r requirements.txt
```

## 快速开始

### 1) 列出当前可用站点

```bash
python main.py list
```

### 2) 下载当前所有可用视频

```bash
python main.py download
```

### 3) 持续监控并自动下载新视频

```bash
python main.py watch
```

## 常用用法

### 按关键词过滤站点

```bash
python main.py --keyword 福田 list
python main.py --keyword 西涌 download
```

### 按 code 过滤站点

```bash
python main.py --codes 73 78 80 list
python main.py --codes 73 78 80 download
```

### JSON 格式输出站点列表

```bash
python main.py list --print-json
```

### 预演下载，不实际写文件

```bash
python main.py --dry-run download
```

### 自定义轮询间隔

```bash
python main.py watch --interval 120
```

### 自定义最小有效文件大小

```bash
python main.py --min-size 1048576 download
```

## 参数说明

- `--out`：输出目录，默认 `./downloads`
- `--state`：状态文件，默认 `./state/state.json`
- `--log-dir`：日志目录，默认 `./logs`
- `--log-level`：日志级别，默认 `INFO`
- `--retry`：请求重试次数，默认 `3`
- `--connect-timeout`：连接超时秒数，默认 `10`
- `--read-timeout`：读取超时秒数，默认 `60`
- `--min-size`：最小有效文件大小（字节），默认 `262144`
- `--keyword`：按观测点名称关键词过滤
- `--codes`：按观测点 code 过滤
- `--dry-run`：仅打印计划，不实际下载

## 输出目录结构

默认运行后会生成如下目录：

```text
.
├── downloads/
│   └── 2026-04-20/
│       └── 73_福田东/
│           └── video_73_202604201119.mp4
├── logs/
│   ├── app.log
│   └── summary-20260420-114500.json
└── state/
    └── state.json
```

说明：
- 视频保存路径为 `downloads/日期/站点目录/视频文件`
- 日期优先取自视频文件名中的时间戳，例如 `video_73_202604201119.mp4` 会归档到 `downloads/2026-04-20/`
- `logs/summary-*.json` 记录每轮执行摘要
- `state/state.json` 记录各站点最近一次看到/下载到的视频状态

## 状态与摘要文件

### state.json

用于记录每个站点最近一次已下载的视频，供 `watch` 模式判断是否有更新。

### summary-*.json

每次执行 `download`，以及 `watch` 模式下的每一轮轮询，都会生成一份摘要文件，记录：
- 执行模式
- 生成时间
- 匹配到的站点数
- 下载 / 跳过 / 失败统计
- 每个站点的处理结果

适合用于：
- 排错
- 留档
- 后续接通知或自动化处理

## 注意事项

1. 站点可用性会变化，`rt_list.js` 返回的站点集合不是固定的。
2. 站点名称或地址偶尔可能受源站编码影响出现乱码，但通常不影响下载逻辑。
3. `watch` 模式适合长期运行；如果只想抓当前一批视频，直接使用 `download` 即可。
4. 下载结果默认不纳入 Git 版本控制，`downloads/`、`logs/`、`state/` 都建议忽略。

## 更新记录（v1 旧版 README 迁移）

### 更新记录

#### 2024/04/23 修改输出提高可读性，修复无法创建文件夹的问题
#### 2024/04/22 更新UA，修复文件不存在不提示问题，修改了输出格式
#### 2024/04/18 由于气象台网站修改了缓存策略，现在能下载到什么时候的视频完全随缘
#### 2023/07/24 由于气象台网站修改了缓存策略，现在只能下载大约 当前时间 3小时 以前的视频
