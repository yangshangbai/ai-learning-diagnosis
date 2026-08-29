#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chrome CDP 看护器（跨平台：Windows 测试环境 / Ubuntu 云端）

职责：
  1. 自动定位本机 Chrome/Chromium；
  2. 用「持久化 user-data-dir」启动带 --remote-debugging-port=9222 的 Chrome，
     登录态(cookie/token)保留在 user-data-dir 内，重启后仍有效；
  3. watchdog 循环：检测 CDP 9222 掉线则自动重新拉起（进程崩溃自愈）；
  4. 所有动作写独立日志 logs/chrome_cdp.log。

用法：
  python chrome_cdp_manager.py --start      启动（若未在跑）
  python chrome_cdp_manager.py --restart    强制重启（先杀后启）
  python chrome_cdp_manager.py --status     打印 CDP 是否可达
  python chrome_cdp_manager.py --watch      常驻看护（后台运行，掉线自动拉起）
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

IS_WIN = platform.system() == "Windows"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CDP_URL = "http://127.0.0.1:9222"
PORT = 9222
USER_DATA_DIR = os.path.join(BASE_DIR, ".chrome_profile")
LOG_FILE = os.path.join(BASE_DIR, "logs", "chrome_cdp.log")
BOUTIQUE_URL = "https://xbresource.jiaoyanyun.com/#/boutique?sid=2&gid=2"


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def find_chrome():
    cands = []
    if IS_WIN:
        cands = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Chromium\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        cands = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    for name in ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _no_proxy_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def cdp_alive(timeout=2):
    try:
        with _no_proxy_opener().open(CDP_URL + "/json/version", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _win_port_pid(port):
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=5).stdout
    except Exception:
        return None
    if not out:
        return None
    # 中文 Windows 下 netstat 输出为 GBK，text=True 会解码失败；这里按 gbk 容错解码
    try:
        text = out.decode("gbk", errors="ignore")
    except Exception:
        text = out.decode("utf-8", errors="ignore")
    for line in text.splitlines():
        if (":%d" % port) in line and "LISTENING" in line:
            parts = line.split()
            if parts and parts[-1].isdigit():
                return int(parts[-1])
    return None


def kill_chrome():
    """只杀占用 9222 调试端口的那个 Chrome 进程，避免误杀用户其它 Chrome。"""
    killed = False
    if IS_WIN:
        pid = _win_port_pid(PORT)
        if pid:
            try:
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(1, False, pid)
                if h:
                    ctypes.windll.kernel32.TerminateProcess(h, 0)
                    ctypes.windll.kernel32.CloseHandle(h)
                    log("已终止占用 9222 的进程 pid=%d" % pid)
                    killed = True
            except Exception as e:
                log("Windows 终止进程失败: %s" % e)
    else:
        # Linux：按命令行精确匹配 remote-debugging-port=9222
        try:
            r = subprocess.run(["pkill", "-f", "remote-debugging-port=9222"],
                               capture_output=True, timeout=5)
            killed = (r.returncode == 0)
            if killed:
                log("已 pkill remote-debugging-port=9222")
        except Exception as e:
            log("Linux pkill 失败: %s" % e)
    return killed


def launch_chrome():
    chrome = find_chrome()
    if not chrome:
        log("未找到 Chrome/Chromium，无法启动 CDP")
        return False
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    args = [
        chrome,
        "--remote-debugging-port=%d" % PORT,
        "--user-data-dir=%s" % USER_DATA_DIR,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
    ]
    if not IS_WIN:
        args.append("--no-sandbox")
        args.append("--disable-gpu")
        if not os.environ.get("DISPLAY"):
            args.insert(1, "--headless=new")
    args.append(BOUTIQUE_URL)
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)
        log("Chrome 已启动 pid=%s (binary=%s, profile=%s)" % (proc.pid, chrome, USER_DATA_DIR))
        return True
    except Exception as e:
        log("Chrome 启动失败: %s" % e)
        return False


def start():
    if cdp_alive():
        log("CDP 已在线，跳过启动")
        return True
    return launch_chrome()


def restart():
    log("手动触发重启 Chrome CDP")
    kill_chrome()
    time.sleep(1.0)
    return launch_chrome()


def watchdog(interval=5):
    log("看护器启动：每 %ds 检测一次 CDP 9222" % interval)
    while True:
        if not cdp_alive():
            log("检测到 CDP 掉线，尝试自动重启…")
            launch_chrome()
        time.sleep(interval)


def status():
    alive = cdp_alive()
    print(json_dumps({"cdp_reachable": alive, "chrome": find_chrome(),
                      "profile": USER_DATA_DIR}))


def json_dumps(o):
    import json
    return json.dumps(o, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", action="store_true")
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=int, default=5)
    args = ap.parse_args()

    if args.start:
        start()
    elif args.restart:
        restart()
    elif args.status:
        status()
    elif args.watch:
        watchdog(args.interval)
    else:
        # 默认：单次 start
        start()


if __name__ == "__main__":
    main()
