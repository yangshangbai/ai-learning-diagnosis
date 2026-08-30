#!/bin/bash
# ============================================================================
# restore_helper.sh — 备份恢复编排（设计稿 v1.1 DR-01，docs/design/备份恢复模块设计.md §4）
#
# 由后端经 systemd-run 触发（后端只触发+轮询，编排全部在本脚本）：
#   sudo systemd-run --unit=ai-restore-<restore_id> --collect \
#        /bin/bash <repo>/scripts/restore_helper.sh <filename> <pre_backup:0/1> <restore_env:0/1> <restore_id>
#
# 输入: $1=备份文件名(白名单校验) $2=pre_backup(0/1) $3=restore_env(0/1) $4=restore_id
# 运行: systemd-run 经 sudo 启动（root 或 ubuntu 均兼容，root 权限路径内部用 sudo）
# 进度: 每步 append 一行 JSON 到 backups/restore_<restore_id>.log，
#       结束行固定 {"step":"done","ok":bool}（由 EXIT trap 保证必写）
#
# 安全护栏:
#   - flock 非阻塞探测 backups/.lock（被占→失败退出；获取后持有全程，与创建/删除互斥 DR-02）
#   - 文件名白名单与后端一致 backup_(program|data|full)_[0-9_]{15}.tar.gz
#   - 外层解包用 python3 tarfile filter="data"（拒绝绝对路径/../软链接，DR-08），部件总量上限 2GB
#   - trap EXIT 保证最终 systemctl start ai-learning（服务不会因恢复失败而停摆）
#
# 运维约束: 恢复窗口内禁止 quick-sync / deploy！
# ============================================================================
set -uo pipefail

APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${AI_BACKUP_DIR:-$APP_ROOT/backups}"   # 生产 = /opt/ai-learning/backups
DB_NAME="ai_training"
BACKUP_FILE=""
FILENAME=""
RESTORE_ID=""
LOG=""
STAGING=""
OK=0                 # 1 = 恢复+健康检查全部成功
PRE_BACKUP_FILE=""

# ---------------------------------------------------------------------------
# 进度输出：emit <step> <true|false> <detail>   （detail 内不得含双引号）
# ---------------------------------------------------------------------------
emit() {
  [ -n "$LOG" ] || return 0
  printf '{"step":"%s","ok":%s,"detail":"%s","ts":"%s"}\n' \
    "$1" "$2" "$3" "$(date '+%Y-%m-%dT%H:%M:%S')" >>"$LOG" 2>/dev/null
}

finish() {
  if [ "$OK" = "1" ]; then
    emit "done" "true" "$FILENAME"
  else
    emit "done" "false" "$FILENAME"
  fi
  [ -n "$STAGING" ] && [ -d "$STAGING" ] && rm -rf "$STAGING"
  # DR-01/§4-6：无论如何保证服务最终拉起
  systemctl start ai-learning >/dev/null 2>&1 || sudo systemctl start ai-learning >/dev/null 2>&1 || true
}
trap finish EXIT

# ---------------------------------------------------------------------------
# pre_backup：本机完整安全备份 backup_full_<ts>.tar.gz（manifest 最后写入）
# 失败返回非 0（调用方中止恢复）
# ---------------------------------------------------------------------------
do_pre_backup() {
  local ts name tmp dump f
  ts="$(date +%Y%m%d_%H%M%S)"
  name="backup_full_${ts}.tar.gz"
  tmp="$(mktemp -d /tmp/ai_prebackup_XXXXXX)"
  dump="/tmp/ai_pgdump_$$.sql.gz"
  rm -f "$dump"

  # db 部件（pg_dump 经 sudo -u postgres，-Z 1 直出 gzip，落 /tmp 再移入）
  if sudo -u postgres pg_dump --clean --if-exists --no-owner -Z 1 -f "$dump" "$DB_NAME" >/dev/null 2>&1 \
     && [ -s "$dump" ]; then
    mv -f "$dump" "$tmp/db.sql.gz"
  else
    rm -f "$dump"
    rm -rf "$tmp"
    echo "pg_dump_failed"
    return 1
  fi

  # program 部件（与后端白名单一致：排 venv/__pycache__/uploads/*.db/.env）
  tar czf "$tmp/program.tar.gz" -C "$APP_ROOT" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='*.db' \
    --exclude='backend/uploads' --exclude='backend/.env' --exclude='backend/venv' --exclude='frontend/node_modules' \
    backend frontend/src frontend/demo/index.html frontend/demo/api-bridge.js \
    frontend/package.json frontend/vite.config.js scripts docs tests \
    jiaoyanyun/*.py jiaoyanyun/*.js \
    AGENTS.md CHANGELOG.md README.md VERSION cloud_migration.md .gitignore \
    >/dev/null 2>&1 || true
  [ -s "$tmp/program.tar.gz" ] || { rm -rf "$tmp"; echo "program_tar_failed"; return 1; }

  # data 其余部件（缺哪个跳哪个）
  tar czf "$tmp/env.tar.gz" -C "$APP_ROOT" backend/.env >/dev/null 2>&1 || rm -f "$tmp/env.tar.gz"
  tar czf "$tmp/uploads.tar.gz" -C "$APP_ROOT" uploads >/dev/null 2>&1 || rm -f "$tmp/uploads.tar.gz"
  tar czf "$tmp/demo_images.tar.gz" -C "$APP_ROOT" frontend/demo/images >/dev/null 2>&1 || rm -f "$tmp/demo_images.tar.gz"
  tar czf "$tmp/jcred.tar.gz" -C "$APP_ROOT" \
    jiaoyanyun/jiaoyanyun_credentials.json jiaoyanyun/jiaoyanyun_token.json >/dev/null 2>&1 || rm -f "$tmp/jcred.tar.gz"

  # manifest（逐部件 sha256+bytes，最后随包写入；格式与后端一致：parts 为数组）
  local parts_json="[" f first=1
  for f in program.tar.gz db.sql.gz env.tar.gz uploads.tar.gz demo_images.tar.gz jcred.tar.gz; do
    [ -f "$tmp/$f" ] || continue
    [ "$first" = "1" ] || parts_json="${parts_json},"
    parts_json="${parts_json}{\"name\":\"${f}\",\"sha256\":\"$(sha256sum "$tmp/$f" | cut -d' ' -f1)\",\"bytes\":$(stat -c%s "$tmp/$f")}"
    first=0
  done
  parts_json="${parts_json}]"
  printf '{"app":"ai-learning","type":"full","version":"%s","created_at":"%s","parts":%s}' \
    "$(cat "$APP_ROOT/VERSION" 2>/dev/null || echo unknown)" \
    "$(date '+%Y-%m-%dT%H:%M:%S')" "$parts_json" >"$tmp/manifest.json"

  # 外层打包（manifest.json 最后加入）
  local list="$tmp/parts.list"
  : >"$list"
  for f in program.tar.gz db.sql.gz env.tar.gz uploads.tar.gz demo_images.tar.gz jcred.tar.gz; do
    [ -f "$tmp/$f" ] && echo "$f" >>"$list"
  done
  echo "manifest.json" >>"$list"
  tar czf "$BACKUP_DIR/$name" -C "$tmp" -T "$list" \
    || { rm -rf "$tmp"; echo "pack_failed"; return 1; }

  chown ubuntu:ubuntu "$BACKUP_DIR/$name" >/dev/null 2>&1 \
    || sudo chown ubuntu:ubuntu "$BACKUP_DIR/$name" >/dev/null 2>&1 || true
  PRE_BACKUP_FILE="$name"
  rm -rf "$tmp"
  return 0
}

# ===========================================================================
# 主流程
# ===========================================================================
if [ "$#" -lt 4 ]; then
  echo "usage: restore_helper.sh <filename> <pre_backup:0/1> <restore_env:0/1> <restore_id>" >&2
  exit 64
fi
FILENAME="$1"; PRE_BACKUP="$2"; RESTORE_ENV="$3"; RESTORE_ID="$4"
# restore_id 字符集守卫（后端生成 [A-Za-z0-9_-]，防手工误用时路径注入）
case "$RESTORE_ID" in
  *[!A-Za-z0-9_-]*) echo "bad restore_id" >&2; exit 64 ;;
esac
LOG="$BACKUP_DIR/restore_${RESTORE_ID}.log"
mkdir -p "$BACKUP_DIR"
touch "$LOG" 2>/dev/null || true
emit "start" "true" "$FILENAME"

# --- 1. flock 非阻塞探测并持有全局锁（DR-02，进程退出自动释放） ---
exec 9>>"$BACKUP_DIR/.lock"
if ! flock -n 9; then
  emit "lock" "false" "backup_or_restore_in_progress"
  exit 1
fi
emit "lock" "true" "acquired"

# --- 2. 文件名白名单 + 存在性（与后端同一正则语义） ---
STEM="${FILENAME%.tar.gz}"
if [ "$STEM" = "$FILENAME" ]; then emit "validate" "false" "bad_ext"; exit 1; fi
TYPE_PART="${STEM#backup_}"
TYPE_NAME="${TYPE_PART%%_*}"
TS="${TYPE_PART#*_}"
case "$TYPE_NAME" in
  program|data|full) : ;;
  *) emit "validate" "false" "bad_filename_type"; exit 1 ;;
esac
if [ "$TYPE_NAME" = "$TS" ] || [ "${#TS}" -ne 15 ]; then
  emit "validate" "false" "bad_filename_ts"
  exit 1
fi
case "$TS" in
  *[!0-9_]*) emit "validate" "false" "bad_filename_charset"; exit 1 ;;
esac
[ -f "$BACKUP_DIR/$FILENAME" ] || { emit "validate" "false" "file_missing"; exit 1; }
BACKUP_FILE="$BACKUP_DIR/$FILENAME"
emit "validate" "true" "$FILENAME"

# --- 3. pre_backup（失败→中止恢复） ---
# 后端在派发前已同步做一次 full 安全备份并写入 pre_backup 进度行 → 去重跳过；
# 仅独立手工调用（日志中无 pre_backup 成功行）时由本脚本自建。
if [ "$PRE_BACKUP" = "1" ]; then
  if grep -q '"step":"pre_backup","ok":true' "$LOG" 2>/dev/null; then
    emit "pre_backup" "true" "already_done_by_backend"
  elif do_pre_backup; then
    emit "pre_backup" "true" "$PRE_BACKUP_FILE"
  else
    emit "pre_backup" "false" "pre_backup_failed"
    exit 1
  fi
else
  emit "pre_backup" "true" "skipped"
fi

# --- 4. 解包 + 校验（python3 tarfile filter="data"，sha256，2GB 上限） ---
STAGING="$(mktemp -d /tmp/ai_restore_XXXXXX)"
PKG_TYPE=""
if ! PKG_TYPE="$(python3 - "$BACKUP_FILE" "$STAGING" <<'PYEOF'
import hashlib, json, os, sys, tarfile

src, dest = sys.argv[1], sys.argv[2]
CAP = 2 * 1024 ** 3  # DR-08: 部件总解压上限 2GB
try:
    with tarfile.open(src, "r:gz") as tar:
        members = tar.getmembers()
        mm = next((m for m in members if m.name == "manifest.json"), None)
        if mm is None:
            sys.exit(3)
        manifest = json.loads(tar.extractfile(mm).read().decode("utf-8"))
        if manifest.get("type") not in ("program", "data", "full"):
            sys.exit(3)
        pmap = {p["name"]: p for p in (manifest.get("parts") or [])}
        data_members = [m for m in members if m.name != "manifest.json"]
        if len(data_members) != len(pmap):
            sys.exit(3)
        for m in data_members:
            if m.name not in pmap or not m.isfile():
                sys.exit(3)
        if sum(m.size for m in data_members) > CAP:
            sys.exit(4)
        for m in data_members:  # sha256 校验（DR-04）
            fh = tar.extractfile(m)
            h = hashlib.sha256()
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
            if h.hexdigest() != (pmap[m.name].get("sha256") or ""):
                sys.exit(5)
        try:  # filter="data"（拒绝绝对路径/..，DR-08）
            tar.extractall(dest, members=data_members, filter="data")
        except TypeError:  # 旧版 Python 无 filter 参数 → 手动等价校验后解包
            for m in data_members:
                n = m.name
                if n.startswith("/") or ".." in n.split("/") or m.issym() or m.islnk():
                    sys.exit(6)
                tar.extract(m, dest)
    print(manifest["type"])
except SystemExit:
    raise
except Exception:
    sys.exit(7)
PYEOF
)"; then
  emit "verify" "false" "package_verify_failed"
  exit 1
fi
emit "verify" "true" "$PKG_TYPE"

# --- 5. program 部件 → 覆盖 /opt/ai-learning（§4-4：tar --overwrite --numeric-owner） ---
PROG_APPLIED=0
if [ -f "$STAGING/program.tar.gz" ]; then
  tar xzf "$STAGING/program.tar.gz" -C "$APP_ROOT" --overwrite --numeric-owner \
    || { emit "program" "false" "tar_failed"; exit 1; }
  emit "program" "true" "applied"
  PROG_APPLIED=1
fi

# --- 6. data 部件 → 停服 → 重建库 → 导入 → 授权 → env/uploads/images/jcred → 拉起 ---
if [ -f "$STAGING/db.sql.gz" ]; then
  sudo systemctl stop ai-learning >/dev/null 2>&1 || sudo systemctl stop ai-learning \
    || { emit "db" "false" "stop_service_failed"; exit 1; }
  emit "db_stop" "true" "ai-learning stopped"

  # 终止残留连接
  sudo -u postgres psql -d "$DB_NAME" \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid<>pg_backend_pid();" \
    >/dev/null 2>&1 || true

  # DROP/CREATE SCHEMA（AUTHORIZATION ai_training，属主归应用账号）
  sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 \
    -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public AUTHORIZATION $DB_NAME;" \
    || { emit "db_schema" "false" "schema_reset_failed"; exit 1; }
  emit "db_schema" "true" "public rebuilt"

  # 导入
  gunzip -c "$STAGING/db.sql.gz" | sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 \
    || { emit "db_import" "false" "psql_import_failed"; exit 1; }
  emit "db_import" "true" "imported"

  # 属主修正 + 授权（DR-07）：弃用 REASSIGN OWNED（波及共享对象必炸——BQ-01）；
  # \gexec 为 psql 元命令在 -c 模式不可用（BQ-01 二次根因），改用 DO 块逐对象 ALTER（单语句 -c 可行）
  GRANT_SQL="ALTER DATABASE $DB_NAME OWNER TO $DB_NAME;
DO \$\$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
    EXECUTE format('ALTER TABLE public.%I OWNER TO $DB_NAME', r.tablename);
  END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname='public' LOOP
    EXECUTE format('ALTER SEQUENCE public.%I OWNER TO $DB_NAME', r.sequencename);
  END LOOP;
  FOR r IN SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' LOOP
    EXECUTE format('ALTER FUNCTION public.%I(%s) OWNER TO $DB_NAME', r.proname, pg_get_function_identity_arguments(r.oid));
  END LOOP;
END
\$\$;
GRANT ALL ON ALL TABLES IN SCHEMA public TO $DB_NAME;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO $DB_NAME;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO $DB_NAME;
GRANT ALL ON SCHEMA public TO $DB_NAME;"
  if ! sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -c "$GRANT_SQL" >/dev/null 2>&1; then
    emit "db_grants" "false" "grant_failed_first_pass"
    # 二次自修：per-table 直接 ALTER（-t -A 去对齐，避免 grep 误判）
    sudo -u postgres psql -d "$DB_NAME" -c "ALTER DATABASE $DB_NAME OWNER TO $DB_NAME;" >/dev/null 2>&1 || true
    sudo -u postgres psql -d "$DB_NAME" -t -A -c "SELECT 'ALTER TABLE public.' || quote_ident(tablename) || ' OWNER TO $DB_NAME;' FROM pg_tables WHERE schemaname='public'" | sudo -u postgres psql -d "$DB_NAME" >/dev/null 2>&1 || true
    sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO $DB_NAME; GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO $DB_NAME; GRANT ALL ON SCHEMA public TO $DB_NAME;" >/dev/null 2>&1 || true
    BAD=$(sudo -u postgres psql -d "$DB_NAME" -t -A -c "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner <> '$DB_NAME'")
    [ "$BAD" = "0" ] || { emit "db_grants" "false" "repair_failed_non_app_tables=$BAD"; exit 1; }
    emit "db_grants" "true" "repaired via per-table fallback"
  fi
  emit "db_grants" "true" "ownership and grants fixed"

  # env 部件：默认跳过 backend/.env（DR-03），restore_env=1 才覆盖
  if [ -f "$STAGING/env.tar.gz" ]; then
    if [ "$RESTORE_ENV" = "1" ]; then
      tar xzf "$STAGING/env.tar.gz" -C "$APP_ROOT" --overwrite --numeric-owner \
        || { emit "env" "false" "tar_failed"; exit 1; }
      emit "env" "true" "restored (all login sessions invalidated)"
    else
      emit "env" "true" "skipped (default, keep current .env)"
    fi
  else
    emit "env" "true" "no env part in package"
  fi

  [ -f "$STAGING/uploads.tar.gz" ] && {
    tar xzf "$STAGING/uploads.tar.gz" -C "$APP_ROOT" --overwrite --numeric-owner \
      || { emit "uploads" "false" "tar_failed"; exit 1; }
    emit "uploads" "true" "applied"
  }
  [ -f "$STAGING/demo_images.tar.gz" ] && {
    tar xzf "$STAGING/demo_images.tar.gz" -C "$APP_ROOT" --overwrite --numeric-owner \
      || { emit "demo_images" "false" "tar_failed"; exit 1; }
    emit "demo_images" "true" "applied"
  }
  [ -f "$STAGING/jcred.tar.gz" ] && {
    tar xzf "$STAGING/jcred.tar.gz" -C "$APP_ROOT" --overwrite --numeric-owner \
      || { emit "jcred" "false" "tar_failed"; exit 1; }
    emit "jcred" "true" "applied"
  }

  sudo systemctl start ai-learning >/dev/null 2>&1 || sudo systemctl start ai-learning \
    || { emit "db" "false" "start_service_failed"; exit 1; }
  emit "service_start" "true" "ai-learning started"

  # DR-10：教研云按需脚本非常驻，提示手动重启
  emit "jiaoyanyun_notice" "true" "教研云 Chrome/令牌如在使用请手动重启"
fi

# --- 7. 仅程序包恢复时重启服务使新代码生效（含 db 的包已在上面 start） ---
if [ "$PROG_APPLIED" = "1" ] && [ ! -f "$STAGING/db.sql.gz" ]; then
  systemctl restart ai-learning >/dev/null 2>&1 || sudo systemctl restart ai-learning \
    || { emit "restart" "false" "restart_failed"; exit 1; }
  emit "restart" "true" "program restored, service restarted"
fi

# --- 8. 健康检查（10 次 x 3s）→ done 行 {ok} ---
HEALTH_OK=0
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -m 5 http://127.0.0.1:8001/health >/dev/null 2>&1; then
    HEALTH_OK=1
    break
  fi
  sleep 3
done
if [ "$HEALTH_OK" = "1" ]; then
  emit "health" "true" "127.0.0.1:8001/health ok"
  OK=1
else
  emit "health" "false" "health_check_failed_after_retries"
fi
