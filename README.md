# Shenzhen Weather Video Downloader

当前版本不再依赖手工猜测视频文件名，而是直接读取页面实际使用的数据源 `rt_list.js`，自动发现当前可用观测点及其最新视频地址，再进行下载或持续监控。

项目地址：
- 页面入口：https://weather.sz.gov.cn/qixiangfuwu/qixiangjiance/shijingjiance/index.html
- 数据列表：https://weather.121.com.cn/data_cache/video/rt/rt_list.js

## 功能特性

- 自动读取当前可用观测点列表
- 支持按观测点名称关键词过滤
- 支持按观测点 code 过滤
- 一次性下载当前视频
- `watch` 模式持续轮询并下载新视频
- 下载时使用 `.part` 临时文件，完成后原子替换
- 自动跳过已存在且大小正常的文件
- 按“视频文件名中的日期”归档，而不是按下载当天归档
- 每轮执行生成 `summary-*.json` 摘要文件
- 保存长期状态到 `state/state.json`
- 控制台 + 文件日志
- 网络请求自动重试

## 目录结构

默认运行后会生成以下目录：

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
- `downloads/日期/站点目录/视频文件`
- 日期优先取自视频文件名中的时间戳，例如 `video_73_202604201119.mp4` 会归档到 `downloads/2026-04-20/`
- `logs/summary-*.json` 记录每轮执行摘要
- `state/state.json` 保存各站点最近一次看到/下载到的视频状态

## 运行环境

- Python 3.9+
- `requests`

安装依赖：

```bash
pip install -r requirements.txt
```

## 用法

### 1. 列出当前所有可用站点

```bash
python main.py list
```

### 2. 按关键词过滤站点

```bash
python main.py --keyword 福田 list
```

### 3. 按 code 过滤站点

```bash
python main.py --codes 73 78 80 list
```

### 4. JSON 格式输出站点列表

```bash
python main.py list --print-json
```

### 5. 一次性下载当前所有可用视频

```bash
python main.py download
```

### 6. 只下载部分站点

```bash
python main.py --keyword 西涌 download
python main.py --codes 73 78 80 download
```

### 7. 预演下载，不实际写文件

```bash
python main.py --dry-run download
```

### 8. 持续监控并自动下载新视频

```bash
python main.py watch
```

### 9. 自定义轮询间隔

```bash
python main.py watch --interval 120
```

### 10. 自定义最小有效文件大小

```bash
python main.py --min-size 1048576 download
```

## 常用参数

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

脚本直接读取这些数据，而不是再按旧逻辑手动拼接时间和文件名。

因此，它能更好地适应：
- 观测点上下线变化
- 页面缓存策略变化
- 各站点视频刷新节奏不一致

## 状态与摘要文件

### state.json

用于记录每个站点最近一次已下载的视频，供 `watch` 模式判断是否有更新。

### summary-*.json

每次执行 `download`，以及 `watch` 模式下的每一轮轮询，都会生成一份摘要文件，记录：
- 执行模式
- 生成时间
- 匹配到的站点数
- 下载/跳过/失败统计
- 每个站点的处理结果

适合用于：
- 排错
- 留档
- 后续通知或自动化处理

## 注意事项

1. 站点可用性会变化，`rt_list.js` 里的站点集合不是固定的。
2. 站点名称/地址偶尔可能受源站编码影响出现乱码，但通常不影响下载逻辑。
3. `watch` 模式适合长期运行；如果仅想抓当前一批视频，使用 `download` 即可。
4. 下载结果默认不纳入 Git 版本控制，`downloads/`、`logs/`、`state/` 都建议忽略。
