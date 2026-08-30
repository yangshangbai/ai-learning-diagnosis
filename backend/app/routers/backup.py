"""系统备份与恢复接口（设计稿 v1.1 · 开发合同，见 docs/design/备份恢复模块设计.md）。

端点（无尾斜杠，挂在 /api/v1/system 下）：
  GET  /api/v1/system/backup/list             备份列表（manifest 校验，坏包标 damaged）
  POST /api/v1/system/backup/create           创建备份 {type: program|data|full}
  GET  /api/v1/system/backup/download         下载备份 ?filename=
  POST /api/v1/system/backup/delete           删除备份 {filename}
  POST /api/v1/system/restore                 触发恢复（异步 202 {restore_id}，systemd-run + restore_helper.sh）
  GET  /api/v1/system/restore/status          恢复进度轮询 ?restore_id=

安全护栏（四条，缺一不可）：
  1. 文件名白名单：backup_(program|data|full)_[0-9_]{15}.tar.gz（list/download/delete/restore 统一校验）
  2. flock 全局互斥：backups/.lock（创建/删除/恢复互斥；helper 内再次持锁）
  3. restore 必须显式 confirm=true（否则 400）
  4. create/restore 前 shutil.disk_usage 检查：空闲 < 2GB 拒绝

包结构：backup_xxx.tar.gz 内含 manifest.json + 各部件（program/db/env/uploads/demo_images/jcred），
每部件含 sha256；manifest.json 最后写入。恢复前强制校验 manifest/type 一致/部件 sha256（DR-04）。
解包安全：后端校验只流式读取不落盘；helper 侧解包用 python tarfile filter="data"（DR-08）。
"""
import datetime
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.errors import AppError, ConflictError, NotFoundError, ValidationError
from ..core.logging import logger
from ..core.security import Principal, require_permission
# 跨模块复用下载响应（Content-Disposition UTF-8 文件名），参照 exam.py 已有写法
from .paper import _download_response

router = APIRouter(prefix="/api/v1/system", tags=["backup"])

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
# 生产固定 /opt/ai-learning/backups；可用环境变量 BACKUP_DIR 覆盖；
# Windows 本地开发默认落到工作目录 tmp_backups（pg_dump/sudo 均不可用，仅做冒烟）
if os.environ.get("BACKUP_DIR"):
    BACKUP_DIR = Path(os.environ["BACKUP_DIR"])
elif os.name == "nt":
    BACKUP_DIR = Path("tmp_backups")
else:
    BACKUP_DIR = Path("/opt/ai-learning/backups")

# 仓库根（routers → app → backend → 仓库根；生产即 /opt/ai-learning）
REPO_ROOT = Path(__file__).resolve().parents[3]
HELPER_PATH = REPO_ROOT / "scripts" / "restore_helper.sh"  # 生产 = /opt/ai-learning/scripts/restore_helper.sh

FILENAME_RE = re.compile(r"backup_(program|data|full)_[0-9_]{15}\.tar\.gz")
RESTORE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")

DB_NAME = "ai_training"
SERVICE_USER = "ubuntu"          # 服务运行用户（已核实，与部署用户一致）
MIN_FREE_BYTES = 2 * 1024 ** 3   # DR-09：磁盘空闲 <2GB 拒绝
PG_DUMP_TIMEOUT = 600            # 合同：pg_dump 超时 600s
SUBPROCESS_TIMEOUT = 60

try:
    import fcntl  # Unix/Linux；Windows 开发环境无此模块（本地冒烟退化为不加锁）
except ImportError:  # pragma: no cover
    fcntl = None


class BackupCreateIn(BaseModel):
    type: Literal["program", "data", "full"]


class BackupDeleteIn(BaseModel):
    filename: str


class RestoreIn(BaseModel):
    filename: str
    confirm: bool = False
    pre_backup: bool = True
    restore_env: bool = False


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def _ensure_backup_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _check_disk() -> None:
    """DR-09：空闲 <2GB 拒绝创建/恢复。"""
    _ensure_backup_dir()
    free = shutil.disk_usage(str(BACKUP_DIR)).free
    if free < MIN_FREE_BYTES:
        raise ValidationError(
            f"磁盘空闲空间不足（剩余 {free / 1024 ** 3:.1f}GB，需至少 2GB），已拒绝操作"
        )


def _validate_filename(filename: Optional[str]) -> str:
    fn = (filename or "").strip()
    if not FILENAME_RE.fullmatch(fn):
        raise ValidationError("非法备份文件名（仅允许 backup_(program|data|full)_时间戳.tar.gz）")
    return fn


@contextmanager
def _backup_lock():
    """flock 全局互斥锁（DR-02）：backups/.lock，进程死自动释放。

    非阻塞获取，被占 → ConflictError（创建/删除/恢复互斥）。
    Windows 开发环境无 fcntl：记录告警后退化为不加锁（仅本地冒烟用）。
    """
    _ensure_backup_dir()
    fh = open(BACKUP_DIR / ".lock", "a+b")
    try:
        if fcntl is None:
            logger.warning("backup_lock_unavailable", extra={"platform": os.name})
            yield
            return
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ConflictError("另一个备份/恢复任务正在进行中，请稍后再试")
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _version() -> str:
    try:
        return (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def _append_progress(restore_id: str, step: str, ok: bool, detail: str) -> None:
    """向 backups/restore_<id>.log 追加一行 JSON 进度。

    与 helper 的 printf 行格式保持一致（紧凑无空格）：
    {"step":"...","ok":true,"detail":"...","ts":"..."} —— helper 依赖
    grep '"step":"pre_backup","ok":true' 去重判断安全备份是否已由后端完成。
    """
    line = json.dumps(
        {
            "step": step,
            "ok": bool(ok),
            "detail": str(detail)[:300],
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    with open(BACKUP_DIR / f"restore_{restore_id}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd: list, timeout: int = SUBPROCESS_TIMEOUT) -> subprocess.CompletedProcess:
    """参数列表 + shell=False（DR-08）。"""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ---------------------------------------------------------------------------
# 部件构建（staging 目录内）
# ---------------------------------------------------------------------------
_EXCLUDE_DIR_NAMES = {"__pycache__", "venv", ".venv", "node_modules"}


def _add_file(tar: tarfile.TarFile, src: Path, arcname: str) -> None:
    if src.is_file():
        tar.add(str(src), arcname=arcname)


def _add_tree(
    tar: tarfile.TarFile,
    src: Path,
    arc_prefix: str,
    exclude_dirs: frozenset = frozenset(),
    exclude_file_exts: frozenset = frozenset(),
    exclude_file_names: frozenset = frozenset(),
) -> None:
    """递归打包目录（排序保证确定性），按目录名/扩展名/文件名排除。"""
    if not src.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(src):
        # 剪枝：全局排除 + 本树排除
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDE_DIR_NAMES and d not in exclude_dirs)
        rel = os.path.relpath(dirpath, src).replace(os.sep, "/")
        arc_dir = arc_prefix if rel == "." else f"{arc_prefix}/{rel}"
        for fn in sorted(filenames):
            if fn in exclude_file_names:
                continue
            if any(fn.endswith(ext) for ext in exclude_file_exts):
                continue
            tar.add(os.path.join(dirpath, fn), arcname=f"{arc_dir}/{fn}")


def _uploads_dir() -> Path:
    """生产 /opt/ai-learning/uploads；本地仓库根 uploads（缺省回落 backend/uploads）。"""
    root = REPO_ROOT / "uploads"
    if root.is_dir():
        return root
    return REPO_ROOT / "backend" / "uploads"


def _build_program_part(dest: Path) -> None:
    """program 部件：backend（排 venv/__pycache__/uploads/*.db/.env）、frontend 代码文件、
    scripts/docs/tests、jiaoyanyun 顶层 *.py *.js、根清单文件（合同 §2）。backend/.env 排除（DR-03）。"""
    with tarfile.open(dest, "w:gz") as tar:
        _add_tree(
            tar,
            REPO_ROOT / "backend",
            "backend",
            exclude_dirs=frozenset({"uploads"}),
            exclude_file_exts=frozenset({".db", ".pyc"}),
            exclude_file_names=frozenset({".env", "dev.db"}),
        )
        _add_tree(tar, REPO_ROOT / "frontend" / "src", "frontend/src")
        _add_file(tar, REPO_ROOT / "frontend" / "demo" / "index.html", "frontend/demo/index.html")
        _add_file(tar, REPO_ROOT / "frontend" / "demo" / "api-bridge.js", "frontend/demo/api-bridge.js")
        _add_file(tar, REPO_ROOT / "frontend" / "package.json", "frontend/package.json")
        _add_file(tar, REPO_ROOT / "frontend" / "vite.config.js", "frontend/vite.config.js")
        _add_tree(tar, REPO_ROOT / "scripts", "scripts", exclude_file_exts=frozenset({".pyc"}))
        _add_tree(tar, REPO_ROOT / "docs", "docs")
        _add_tree(tar, REPO_ROOT / "tests", "tests", exclude_file_exts=frozenset({".pyc"}))
        jy = REPO_ROOT / "jiaoyanyun"
        if jy.is_dir():
            for pat in ("*.py", "*.js"):
                for p in sorted(jy.glob(pat)):
                    if p.is_file():
                        tar.add(str(p), arcname=f"jiaoyanyun/{p.name}")
        for name in ("AGENTS.md", "CHANGELOG.md", "README.md", "VERSION", "cloud_migration.md", ".gitignore"):
            _add_file(tar, REPO_ROOT / name, name)


def _build_db_part(dest: Path) -> None:
    """db.sql.gz：pg_dump --clean --if-exists --no-owner -Z 1（gzip 压缩）。

    流程（合同要点）：pg_dump 经 sudo -u postgres 先落 /tmp（-f 直出 gzip，省管道），
    再 sudo chown ubuntu 后移入部件目录——避免 -f 产物属主是 postgres 的权限坑。
    全部 subprocess 用参数列表 + shell=False，超时 600s。
    """
    if os.name == "nt":
        # 本地 Windows 开发（SQLite、无 sudo/pg_dump）：跳过数据库部件（生产 Linux 不受影响）
        logger.warning("backup_pg_dump_skipped_windows_dev")
        return
    tmp = f"/tmp/ai_backup_db_{os.getpid()}_{int(datetime.datetime.now().timestamp())}.sql.gz"
    cmd = [
        "sudo", "-u", "postgres", "pg_dump",
        "--clean", "--if-exists", "--no-owner",
        "-Z", "1",
        "-f", tmp,
        DB_NAME,
    ]
    try:
        proc = _run(cmd, timeout=PG_DUMP_TIMEOUT)
        if proc.returncode != 0:
            raise ConflictError(f"pg_dump 失败：{(proc.stderr or proc.stdout or '').strip()[:300]}")
        _run(["sudo", "chown", SERVICE_USER, tmp])
        src = Path(tmp)
        if not src.is_file() or src.stat().st_size == 0:
            raise ConflictError("pg_dump 未产出数据文件")
        with open(src, "rb") as f:
            magic = f.read(2)
        if magic == b"\x1f\x8b":  # -Z 1 预期直出 gzip
            shutil.move(str(src), str(dest))
        else:
            # 环境不支持 -f 压缩时产出纯 SQL → 这里补一道 gzip
            with open(src, "rb") as fin, gzip.open(dest, "wb") as fout:
                shutil.copyfileobj(fin, fout, length=1024 * 1024)
            try:
                os.remove(src)
            except OSError:
                pass
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                _run(["sudo", "rm", "-f", tmp])


def _build_env_part(dest: Path) -> None:
    """env 部件：backend/.env（仅 data/full；.env 只允许出现在 data 包，DR-03）。"""
    env = REPO_ROOT / "backend" / ".env"
    if not env.is_file():
        logger.warning("backup_env_part_missing", extra={"path": str(env)})
        return
    with tarfile.open(dest, "w:gz") as tar:
        tar.add(str(env), arcname="backend/.env")


def _build_uploads_part(dest: Path) -> None:
    src = _uploads_dir()
    if not src.is_dir():
        raise ValidationError(f"uploads 目录不存在：{src}")
    with tarfile.open(dest, "w:gz") as tar:
        _add_tree(tar, src, "uploads")


def _build_demo_images_part(dest: Path) -> None:
    _add_tree_safe(dest, REPO_ROOT / "frontend" / "demo" / "images", "frontend/demo/images")


def _build_jcred_part(dest: Path) -> None:
    """jcred 部件：jiaoyanyun_credentials.json + jiaoyanyun_token.json（缺哪个跳哪个，全缺则无部件）。"""
    pairs = [
        (REPO_ROOT / "jiaoyanyun" / "jiaoyanyun_credentials.json", "jiaoyanyun/jiaoyanyun_credentials.json"),
        (REPO_ROOT / "jiaoyanyun" / "jiaoyanyun_token.json", "jiaoyanyun/jiaoyanyun_token.json"),
    ]
    existing = [(p, a) for p, a in pairs if p.is_file()]
    if not existing:
        return
    with tarfile.open(dest, "w:gz") as tar:
        for p, a in existing:
            tar.add(str(p), arcname=a)


def _add_tree_safe(dest: Path, src: Path, arc_prefix: str) -> None:
    if not src.is_dir():
        return
    with tarfile.open(dest, "w:gz") as tar:
        _add_tree(tar, src, arc_prefix)


# ---------------------------------------------------------------------------
# 打包 & 校验
# ---------------------------------------------------------------------------
def _pack_backup(dest: Path, staging: Path, part_names: list, manifest: dict) -> None:
    """外层 tar.gz：部件在前，manifest.json 最后写入（DR-04）。"""
    manifest_path = staging / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with tarfile.open(dest, "w:gz") as tar:
        for name in part_names:
            tar.add(str(staging / name), arcname=name)
        tar.add(str(manifest_path), arcname="manifest.json")  # 最后写入


def _create_backup_internal(btype: str) -> str:
    """备份核心实现（自行加锁 + 磁盘检查 + 失败清理半成品）。返回生成的文件名。"""
    if btype not in ("program", "data", "full"):
        raise ValidationError("type 仅允许 program/data/full")
    _ensure_backup_dir()
    with _backup_lock():
        _check_disk()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # 14 位数字+1 下划线 = 15 字符
        filename = f"backup_{btype}_{ts}.tar.gz"
        dest = BACKUP_DIR / filename
        staging = Path(tempfile.mkdtemp(prefix=".staging_", dir=str(BACKUP_DIR)))
        try:
            parts: list = []
            if btype in ("program", "full"):
                _build_program_part(staging / "program.tar.gz")
                parts.append("program.tar.gz")
            if btype in ("data", "full"):
                _build_db_part(staging / "db.sql.gz")
                if (staging / "db.sql.gz").is_file():
                    parts.append("db.sql.gz")
                elif os.name != "nt":
                    raise ConflictError("pg_dump 未产出数据库部件，备份已中止")
                else:
                    logger.warning("backup_data_without_db_windows_dev")
                _build_env_part(staging / "env.tar.gz")
                if (staging / "env.tar.gz").is_file():
                    parts.append("env.tar.gz")
                _build_uploads_part(staging / "uploads.tar.gz")
                parts.append("uploads.tar.gz")
                _build_demo_images_part(staging / "demo_images.tar.gz")
                if (staging / "demo_images.tar.gz").is_file():
                    parts.append("demo_images.tar.gz")
                _build_jcred_part(staging / "jcred.tar.gz")
                if (staging / "jcred.tar.gz").is_file():
                    parts.append("jcred.tar.gz")
            if not parts:
                raise ValidationError("没有可打包的备份内容")
            # 逐部件 sha256 → manifest（最后随包写入）
            manifest = {
                "app": "ai-learning",
                "type": btype,
                "version": _version(),
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "parts": [
                    {
                        "name": name,
                        "sha256": _sha256_of(staging / name),
                        "bytes": (staging / name).stat().st_size,
                    }
                    for name in parts
                ],
            }
            _pack_backup(dest, staging, parts, manifest)
        except Exception:
            # 失败清理半成品（staging + 未完成的外层包）
            shutil.rmtree(staging, ignore_errors=True)
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            raise
        shutil.rmtree(staging, ignore_errors=True)
    logger.info(
        "backup_created",
        extra={"file": filename, "backup_type": btype, "size_bytes": dest.stat().st_size},
    )
    return filename


def _verify_package(path: Path):
    """恢复前强校验（DR-04）：manifest 存在 / type 与文件名一致 / 部件齐全且 sha256 匹配。

    只流式读取（extractfile），不落盘解包——无路径穿越面。
    返回 (type, manifest)。
    """
    try:
        with tarfile.open(path, "r:gz") as tar:
            members = tar.getmembers()
            manifest_member = next((m for m in members if m.name == "manifest.json"), None)
            if manifest_member is None:
                raise ValidationError("备份包缺少 manifest.json，已拒绝恢复")
            manifest = json.loads(tar.extractfile(manifest_member).read().decode("utf-8"))
            mtype = manifest.get("type")
            if mtype not in ("program", "data", "full"):
                raise ValidationError("manifest.type 非法")
            if path.name.split("_")[1] != mtype:
                raise ValidationError("文件名类型与 manifest.type 不一致，已拒绝恢复")
            declared = manifest.get("parts") or []
            if not declared:
                raise ValidationError("manifest.parts 为空")
            by_name = {m.name: m for m in members}
            for part in declared:
                name = part.get("name")
                member = by_name.get(name)
                if member is None:
                    raise ValidationError(f"备份包缺少部件 {name}，已拒绝恢复")
                fh = tar.extractfile(member)
                if fh is None:
                    raise ValidationError(f"部件 {name} 无法读取，已拒绝恢复")
                h = hashlib.sha256()
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
                if h.hexdigest() != (part.get("sha256") or ""):
                    raise ValidationError(f"部件 {name} sha256 校验失败，备份包已损坏")
        return mtype, manifest
    except (ValidationError, ConflictError):
        raise
    except Exception as exc:
        raise ValidationError(f"备份包已损坏，无法恢复：{exc}")


# ---------------------------------------------------------------------------
# 六个端点
# ---------------------------------------------------------------------------
@router.get("/backup/list")
def list_backups(_: Principal = Depends(require_permission("system", "view"))):
    """扫描备份目录；manifest 完整性校验，缺/坏标 damaged（不列入可恢复）。"""
    _ensure_backup_dir()
    items = []
    for p in sorted(BACKUP_DIR.glob("backup_*.tar.gz"), reverse=True):
        if not FILENAME_RE.fullmatch(p.name):
            continue  # 白名单外直接忽略
        info = {
            "filename": p.name,
            "type": None,
            "version": None,
            "created_at": None,
            "size_bytes": p.stat().st_size,
            "damaged": False,
        }
        try:
            with tarfile.open(p, "r:gz") as tar:
                names = {m.name for m in tar.getmembers()}
                if "manifest.json" not in names:
                    raise ValueError("missing manifest")
                raw = tar.extractfile("manifest.json")
                if raw is None:
                    raise ValueError("manifest unreadable")
                mf = json.loads(raw.read().decode("utf-8"))
                mtype = mf.get("type")
                if mtype not in ("program", "data", "full"):
                    raise ValueError("bad manifest type")
                if p.name.split("_")[1] != mtype:
                    raise ValueError("manifest type mismatch")
                for part in mf.get("parts") or []:
                    if part.get("name") not in names:
                        raise ValueError(f"missing part {part.get('name')}")
                info.update(
                    type=mtype,
                    version=mf.get("version"),
                    created_at=mf.get("created_at"),
                )
        except Exception:
            info["damaged"] = True
        items.append(info)
    return items


@router.post("/backup/create")
def create_backup(
    body: BackupCreateIn, _: Principal = Depends(require_permission("system", "edit"))
):
    """创建备份：flock → 磁盘检查 → 组装部件（subprocess 列表参数 shell=False）→
    逐部件 sha256 → 最后写 manifest → 失败清理半成品并释放锁。"""
    filename = _create_backup_internal(body.type)
    dest = BACKUP_DIR / filename
    return {"filename": filename, "type": body.type, "size_bytes": dest.stat().st_size}


@router.get("/backup/download")
def download_backup(
    filename: str = Query(...), _: Principal = Depends(require_permission("system", "view"))
):
    fn = _validate_filename(filename)  # 白名单：拒绝 ../../etc/passwd 等
    path = BACKUP_DIR / fn
    if not path.is_file():
        raise NotFoundError("备份文件", fn)
    return _download_response(str(path), fn, media_type="application/gzip")


@router.post("/backup/delete")
def delete_backup(
    body: BackupDeleteIn, _: Principal = Depends(require_permission("system", "edit"))
):
    fn = _validate_filename(body.filename)
    with _backup_lock():
        path = BACKUP_DIR / fn
        if not path.is_file():
            raise NotFoundError("备份文件", fn)
        path.unlink()
    logger.info("backup_deleted", extra={"file": fn})
    return {"code": 0, "message": "deleted", "data": None}


@router.post("/restore")
def trigger_restore(
    body: RestoreIn, _: Principal = Depends(require_permission("system", "edit"))
):
    """触发恢复（DR-01 异步编排）：

    confirm 必须 true（否则 400）→ 磁盘检查 → 包完整性强校验（manifest/type/sha256）→
    （可选）先做一次 full 安全备份并把文件名写入进度 → 写首条进度行 →
    sudo systemd-run --unit=ai-restore-<id> --collect /bin/bash restore_helper.sh ...
    → 202 {restore_id}
    """
    if body.confirm is not True:
        raise AppError("未确认恢复操作（confirm 必须为 true）", "BAD_REQUEST", 400)
    fn = _validate_filename(body.filename)
    _ensure_backup_dir()
    path = BACKUP_DIR / fn
    if not path.is_file():
        raise NotFoundError("备份文件", fn)
    _check_disk()
    if not HELPER_PATH.is_file():
        raise ValidationError(f"恢复脚本缺失：{HELPER_PATH}")
    _, manifest = _verify_package(path)

    # 触发时锁探测（非阻塞，拿了就放；helper 内会再次持锁完成互斥）
    with _backup_lock():
        pass

    restore_id = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"

    # （可选）恢复前安全备份：失败即中止恢复
    pre_file = None
    if body.pre_backup:
        try:
            pre_file = _create_backup_internal("full")
            _append_progress(restore_id, "pre_backup", True, pre_file)
        except Exception as exc:
            logger.error("restore_pre_backup_failed", extra={"err": str(exc)[:300]})
            _append_progress(restore_id, "pre_backup", False, str(exc)[:200])
            _append_progress(restore_id, "done", False, "恢复前安全备份失败，已中止恢复")
            raise ConflictError(f"恢复前安全备份失败，已中止恢复：{exc}")
    else:
        _append_progress(restore_id, "pre_backup", True, "skipped（未勾选安全备份）")

    # 写首条 dispatch 进度行后触发 systemd-run
    _append_progress(restore_id, "dispatch", True, fn)
    cmd = [
        "sudo", "systemd-run",
        f"--unit=ai-restore-{restore_id}",
        "--collect",
        "/bin/bash", str(HELPER_PATH),
        fn,
        "1" if body.pre_backup else "0",
        "1" if body.restore_env else "0",
        restore_id,
    ]
    try:
        proc = _run(cmd)
    except subprocess.TimeoutExpired:
        _append_progress(restore_id, "dispatch", False, "systemd-run 超时")
        _append_progress(restore_id, "done", False, "恢复任务触发失败（systemd-run 超时）")
        raise ConflictError("恢复任务触发失败：systemd-run 超时")
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:200] or "unknown"
        _append_progress(restore_id, "dispatch", False, err)
        _append_progress(restore_id, "done", False, "恢复任务触发失败")
        logger.error("restore_trigger_failed", extra={"restore_id": restore_id, "err": err})
        raise ConflictError(f"恢复任务触发失败：{err}")

    logger.info(
        "restore_triggered",
        extra={
            "restore_id": restore_id,
            "file": fn,
            "parts": [p.get("name") for p in manifest.get("parts", [])],
            "pre_backup": pre_file,
            "restore_env": bool(body.restore_env),
        },
    )
    return JSONResponse(
        status_code=202,
        content={
            "code": 0,
            "restore_id": restore_id,
            "pre_backup_file": pre_file,
            "message": "恢复任务已启动，请轮询 status 获取进度",
        },
    )


@router.get("/restore/status")
def restore_status(
    restore_id: str = Query(...), _: Principal = Depends(require_permission("system", "view"))
):
    """读 backups/restore_<id>.log（每行 JSON step）→ {done, ok, steps}。"""
    rid = (restore_id or "").strip()
    if not RESTORE_ID_RE.fullmatch(rid):
        raise ValidationError("非法 restore_id")
    log_path = BACKUP_DIR / f"restore_{rid}.log"
    if not log_path.is_file():
        raise NotFoundError("恢复任务", rid)
    steps = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # 跳过半行/脏行
    done = False
    ok = False
    for s in steps:
        if s.get("step") == "done":
            done = True
            ok = bool(s.get("ok"))
    return {"restore_id": rid, "done": done, "ok": ok, "steps": steps}
