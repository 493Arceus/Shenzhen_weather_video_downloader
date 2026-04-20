#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RT_LIST_URL = "https://weather.121.com.cn/data_cache/video/rt/rt_list.js"
BASE_URL = "https://weather.121.com.cn/data_cache/"
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class Station:
    code: str
    name: str
    mp4_rel: str
    mp4_url: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    height: Optional[float] = None
    addr: str = ""


class AppError(Exception):
    pass


def now_local_str() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sanitize_filename(name: str) -> str:
    if not name:
        return "unknown"
    bad = '\\/:*?"<>|\r\n\t'
    for ch in bad:
        name = name.replace(ch, "_")
    return re.sub(r"\s+", " ", name).strip() or "unknown"


def parse_video_datetime_from_mp4_rel(mp4_rel: str) -> Optional[datetime]:
    filename = Path(mp4_rel).name
    match = re.search(r"video_\d+_(\d{12})\.mp4$", filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d%H%M")
    except ValueError:
        return None


def get_archive_date_dir(mp4_rel: str) -> str:
    dt = parse_video_datetime_from_mp4_rel(mp4_rel)
    if dt is not None:
        return dt.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def setup_logger(log_dir: Path, level: str = "INFO") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sz_weather_video_downloader")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def build_session(
    retries: int = 3,
    backoff_factor: float = 1.0,
    user_agent: str = DEFAULT_UA,
) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": user_agent})
    return session


def decode_response_text(resp: requests.Response) -> str:
    if resp.encoding and resp.encoding.lower() not in ("iso-8859-1", "ascii"):
        return resp.text

    candidates = []
    if getattr(resp, "apparent_encoding", None):
        candidates.append(resp.apparent_encoding)
    candidates.extend(["gb18030", "gbk", "utf-8"])

    for enc in candidates:
        try:
            return resp.content.decode(enc)
        except Exception:
            continue
    return resp.content.decode("utf-8", errors="replace")


def parse_sz121_js(js_text: str) -> Any:
    m = re.search(r"var\s+SZ121_DATA\s*=\s*(.*?);?\s*}\s*catch", js_text, re.S)
    if not m:
        raise AppError("未找到 SZ121_DATA 数据段")
    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise AppError(f"SZ121_DATA JSON 解析失败: {e}") from e


def normalize_station(item: Dict[str, Any]) -> Station:
    code = str(item.get("code", "")).strip()
    name = str(item.get("name", "") or "").strip()
    mp4_rel = str(item.get("mp4", "") or "").strip()
    return Station(
        code=code,
        name=name or code or "unknown",
        mp4_rel=mp4_rel,
        mp4_url=(BASE_URL + mp4_rel) if mp4_rel else "",
        latitude=item.get("latitude"),
        longitude=item.get("longitude"),
        height=item.get("height"),
        addr=str(item.get("addr", "") or "").strip(),
    )


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def station_tag(st: Station) -> str:
    return f"[{st.code} {st.name}]"


class SummaryWriter:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir

    def write(self, payload: Dict[str, Any]) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.log_dir / f"summary-{ts}.json"
        save_json(path, payload)
        return path


class Client:
    def __init__(self, session: requests.Session, timeout: Tuple[int, int], logger: logging.Logger):
        self.session = session
        self.timeout = timeout
        self.logger = logger

    def fetch_text(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise AppError(f"请求失败 {url} -> HTTP {resp.status_code}")
        return decode_response_text(resp)

    def get_rt_list(self) -> List[Station]:
        text = self.fetch_text(RT_LIST_URL)
        data = parse_sz121_js(text)
        if not isinstance(data, list):
            raise AppError("rt_list.js 返回的不是列表")
        return [normalize_station(x) for x in data if isinstance(x, dict)]


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = load_json(path, {"_meta": {}, "stations": {}})
        if not isinstance(self.data, dict):
            self.data = {"_meta": {}, "stations": {}}
        self.data.setdefault("_meta", {})
        self.data.setdefault("stations", {})

    def get_last_mp4(self, code: str) -> Optional[str]:
        item = self.data["stations"].get(code, {})
        return item.get("last_mp4")

    def update_station(self, st: Station, *, last_mp4: str, last_file: str, last_size: int) -> None:
        self.data["stations"][st.code] = {
            "name": st.name,
            "last_mp4": last_mp4,
            "last_seen_at": now_local_str(),
            "last_download_at": now_local_str(),
            "last_file": last_file,
            "last_size": last_size,
            "latitude": st.latitude,
            "longitude": st.longitude,
            "height": st.height,
            "addr": st.addr,
        }

    def touch_seen(self, st: Station) -> None:
        item = self.data["stations"].setdefault(st.code, {})
        item["name"] = st.name
        item["last_seen_at"] = now_local_str()
        item["latitude"] = st.latitude
        item["longitude"] = st.longitude
        item["height"] = st.height
        item["addr"] = st.addr

    def set_meta(self, **kwargs: Any) -> None:
        self.data["_meta"].update(kwargs)

    def save(self) -> None:
        save_json(self.path, self.data)


class Downloader:
    def __init__(
        self,
        session: requests.Session,
        logger: logging.Logger,
        min_size: int = 256 * 1024,
        timeout: Tuple[int, int] = (10, 60),
        dry_run: bool = False,
    ):
        self.session = session
        self.logger = logger
        self.min_size = min_size
        self.timeout = timeout
        self.dry_run = dry_run

    def build_dest_path(self, out_dir: Path, st: Station, mp4_rel: str) -> Path:
        date_dir = get_archive_date_dir(mp4_rel)
        station_dir = f"{st.code}_{sanitize_filename(st.name)}"
        filename = Path(mp4_rel).name
        return out_dir / date_dir / station_dir / filename

    def should_skip_existing(self, dest: Path) -> bool:
        if not dest.exists():
            return False
        try:
            size = dest.stat().st_size
        except Exception:
            return False
        if size >= self.min_size:
            return True
        self.logger.warning(f"已存在文件过小，删除重下: {dest} ({size} bytes)")
        try:
            dest.unlink()
        except Exception:
            pass
        return False

    def download(self, st: Station, out_dir: Path) -> Tuple[str, Optional[Path], Optional[int], str]:
        if not st.mp4_url or not st.mp4_rel:
            return "no_mp4", None, None, "无 mp4 地址"

        dest = self.build_dest_path(out_dir, st, st.mp4_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if self.should_skip_existing(dest):
            return "skipped_existing", dest, dest.stat().st_size, "文件已存在"

        tmp = dest.with_suffix(dest.suffix + ".part")

        if self.dry_run:
            return "dry_run", dest, None, f"将下载 {st.mp4_url}"

        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass

        try:
            with self.session.get(st.mp4_url, timeout=self.timeout, stream=True) as resp:
                if resp.status_code != 200:
                    return "failed", None, None, f"下载失败 HTTP {resp.status_code}"

                expected_len = resp.headers.get("Content-Length")
                expected_size = int(expected_len) if expected_len and expected_len.isdigit() else None

                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())

            actual_size = tmp.stat().st_size if tmp.exists() else 0

            if expected_size is not None and actual_size != expected_size:
                try:
                    tmp.unlink()
                except Exception:
                    pass
                return "failed", None, actual_size, f"文件大小不匹配 expected={expected_size}, actual={actual_size}"

            if actual_size < self.min_size:
                try:
                    tmp.unlink()
                except Exception:
                    pass
                return "failed", None, actual_size, f"文件过小，低于阈值 {self.min_size} bytes"

            tmp.replace(dest)
            return "downloaded", dest, actual_size, "下载成功"

        except Exception as e:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            return "failed", None, None, f"异常: {e}"


def filter_stations(stations: List[Station], codes: Optional[List[str]] = None, keyword: Optional[str] = None) -> List[Station]:
    code_set = set(str(x).strip() for x in (codes or []) if str(x).strip())
    keyword = keyword.strip() if keyword else None
    result = []
    for st in stations:
        if code_set and st.code not in code_set:
            continue
        if keyword and keyword not in st.name:
            continue
        result.append(st)
    return result


def list_stations(stations: List[Station], print_json: bool = False) -> None:
    if print_json:
        print(json.dumps([asdict(st) for st in stations], ensure_ascii=False, indent=2))
        return
    for st in stations:
        print(f"[{st.code}] {st.name} | height={st.height} | mp4={st.mp4_url}")


def make_result_item(st: Station, status: str, message: str, dest: Optional[Path] = None, size: Optional[int] = None) -> Dict[str, Any]:
    return {
        "code": st.code,
        "name": st.name,
        "mp4_rel": st.mp4_rel,
        "mp4_url": st.mp4_url,
        "archive_date": get_archive_date_dir(st.mp4_rel) if st.mp4_rel else None,
        "status": status,
        "message": message,
        "file_path": str(dest) if dest else None,
        "file_size": size,
    }


def write_summary(summary_writer: SummaryWriter, payload: Dict[str, Any], logger: logging.Logger) -> Path:
    path = summary_writer.write(payload)
    logger.info(f"本轮摘要已写入: {path}")
    return path


def run_list(args, client: Client) -> int:
    stations = filter_stations(client.get_rt_list(), codes=args.codes, keyword=args.keyword)
    list_stations(stations, print_json=args.print_json)
    return 0


def run_download(args, client: Client, downloader: Downloader, state: StateStore, logger: logging.Logger, summary_writer: SummaryWriter) -> int:
    stations = filter_stations(client.get_rt_list(), codes=args.codes, keyword=args.keyword)
    if not stations:
        logger.warning("没有匹配到可用观测点")
        return 1

    results = []
    counts = {"downloaded": 0, "skipped_existing": 0, "dry_run": 0, "failed": 0, "no_mp4": 0}

    for st in stations:
        state.touch_seen(st)
        if not st.mp4_rel:
            logger.warning(f"{station_tag(st)} 当前无 mp4")
            results.append(make_result_item(st, "no_mp4", "当前无 mp4"))
            counts["no_mp4"] += 1
            continue

        logger.info(f"{station_tag(st)} 当前视频: {st.mp4_rel}")
        status, dest, size, msg = downloader.download(st, Path(args.out))

        if status == "downloaded":
            logger.info(f"{station_tag(st)} 下载完成: {dest} ({size} bytes)")
            state.update_station(st, last_mp4=st.mp4_rel, last_file=str(dest), last_size=size or 0)
        elif status == "skipped_existing":
            logger.info(f"{station_tag(st)} 跳过: {dest}")
        elif status == "dry_run":
            logger.info(f"{station_tag(st)} dry-run: {msg}")
        elif status == "failed":
            logger.error(f"{station_tag(st)} 下载失败: {msg}")
        elif status == "no_mp4":
            logger.warning(f"{station_tag(st)} 无 mp4")

        counts.setdefault(status, 0)
        counts[status] += 1
        results.append(make_result_item(st, status, msg, dest=dest, size=size))

    state.set_meta(last_poll_at=now_local_str(), source=RT_LIST_URL)
    state.save()

    summary = {
        "mode": "download",
        "generated_at": now_local_str(),
        "source": RT_LIST_URL,
        "matched_station_count": len(stations),
        "counts": counts,
        "results": results,
    }
    write_summary(summary_writer, summary, logger)

    logger.info(
        "执行完成: downloaded=%s skipped_existing=%s dry_run=%s no_mp4=%s failed=%s"
        % (
            counts.get("downloaded", 0),
            counts.get("skipped_existing", 0),
            counts.get("dry_run", 0),
            counts.get("no_mp4", 0),
            counts.get("failed", 0),
        )
    )
    return 0 if counts.get("failed", 0) == 0 else 2


def run_watch(args, client: Client, downloader: Downloader, state: StateStore, logger: logging.Logger, summary_writer: SummaryWriter) -> int:
    logger.info(f"开始监控，轮询间隔 {args.interval} 秒")
    while True:
        results = []
        counts = {
            "downloaded": 0,
            "skipped_existing": 0,
            "dry_run": 0,
            "failed": 0,
            "no_mp4": 0,
            "unchanged": 0,
        }
        try:
            stations = filter_stations(client.get_rt_list(), codes=args.codes, keyword=args.keyword)
            logger.info(f"本轮获取到 {len(stations)} 个站点")

            for st in stations:
                try:
                    state.touch_seen(st)
                    if not st.mp4_rel:
                        logger.warning(f"{station_tag(st)} 当前无 mp4")
                        counts["no_mp4"] += 1
                        results.append(make_result_item(st, "no_mp4", "当前无 mp4"))
                        continue

                    last_mp4 = state.get_last_mp4(st.code)
                    if last_mp4 == st.mp4_rel:
                        logger.info(f"{station_tag(st)} 无更新")
                        counts["unchanged"] += 1
                        results.append(make_result_item(st, "unchanged", "无更新"))
                        continue

                    logger.info(f"{station_tag(st)} 发现新视频: {st.mp4_rel}")
                    status, dest, size, msg = downloader.download(st, Path(args.out))

                    if status == "downloaded":
                        logger.info(f"{station_tag(st)} 下载完成: {dest} ({size} bytes)")
                        state.update_station(st, last_mp4=st.mp4_rel, last_file=str(dest), last_size=size or 0)
                    elif status == "skipped_existing":
                        logger.info(f"{station_tag(st)} 文件已存在: {dest}")
                        if dest is not None:
                            try:
                                existing_size = dest.stat().st_size if dest.exists() else 0
                            except Exception:
                                existing_size = 0
                            state.update_station(st, last_mp4=st.mp4_rel, last_file=str(dest), last_size=existing_size)
                    elif status == "dry_run":
                        logger.info(f"{station_tag(st)} dry-run: {msg}")
                    elif status == "failed":
                        logger.error(f"{station_tag(st)} 下载失败: {msg}")

                    counts.setdefault(status, 0)
                    counts[status] += 1
                    results.append(make_result_item(st, status, msg, dest=dest, size=size))

                except Exception as e:
                    logger.error(f"{station_tag(st)} 单站点处理异常: {e}")
                    counts["failed"] += 1
                    results.append(make_result_item(st, "failed", f"单站点处理异常: {e}"))

            state.set_meta(last_poll_at=now_local_str(), source=RT_LIST_URL)
            state.save()

            summary = {
                "mode": "watch",
                "generated_at": now_local_str(),
                "source": RT_LIST_URL,
                "matched_station_count": len(stations),
                "counts": counts,
                "results": results,
            }
            write_summary(summary_writer, summary, logger)

        except Exception as e:
            logger.error(f"本轮轮询失败: {e}")
            summary = {
                "mode": "watch",
                "generated_at": now_local_str(),
                "source": RT_LIST_URL,
                "matched_station_count": 0,
                "counts": counts,
                "results": results,
                "error": str(e),
            }
            write_summary(summary_writer, summary, logger)

        time.sleep(args.interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="深圳气象实景监测视频下载器 v2")
    parser.add_argument("--out", default="./downloads", help="输出目录，默认 ./downloads")
    parser.add_argument("--state", default="./state/state.json", help="状态文件，默认 ./state/state.json")
    parser.add_argument("--log-dir", default="./logs", help="日志目录，默认 ./logs")
    parser.add_argument("--log-level", default="INFO", help="日志级别: DEBUG/INFO/WARNING/ERROR")
    parser.add_argument("--retry", type=int, default=3, help="重试次数，默认 3")
    parser.add_argument("--connect-timeout", type=int, default=10, help="连接超时秒数，默认 10")
    parser.add_argument("--read-timeout", type=int, default=60, help="读取超时秒数，默认 60")
    parser.add_argument("--min-size", type=int, default=256 * 1024, help="最小有效文件大小(bytes)，默认 262144")
    parser.add_argument("--keyword", help="按名称关键词过滤，如 福田")
    parser.add_argument("--codes", nargs="*", help="按 code 过滤，如 73 78 80")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划，不实际下载")

    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list", help="列出当前可用观测点")
    p_list.add_argument("--print-json", action="store_true", help="JSON 格式输出")
    sub.add_parser("download", help="下载当前可用视频")
    p_watch = sub.add_parser("watch", help="持续监控并下载新视频")
    p_watch.add_argument("--interval", type=int, default=60, help="轮询间隔秒，默认 60")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logger = setup_logger(Path(args.log_dir), args.log_level)
    session = build_session(retries=args.retry)
    timeout = (args.connect_timeout, args.read_timeout)

    client = Client(session=session, timeout=timeout, logger=logger)
    downloader = Downloader(session=session, logger=logger, min_size=args.min_size, timeout=timeout, dry_run=args.dry_run)
    state = StateStore(Path(args.state))
    summary_writer = SummaryWriter(Path(args.log_dir))

    try:
        if args.cmd == "list":
            return run_list(args, client)
        if args.cmd == "download":
            return run_download(args, client, downloader, state, logger, summary_writer)
        if args.cmd == "watch":
            return run_watch(args, client, downloader, state, logger, summary_writer)
        parser.print_help()
        return 1
    except KeyboardInterrupt:
        logger.warning("用户中断")
        return 130
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
