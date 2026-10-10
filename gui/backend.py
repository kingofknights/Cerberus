"""App backend: plain functions over the tested core (inputs, pipeline, db) plus one background Job.

Every function returns plain dicts/lists so the UI layer stays thin. Long work (builds, uploads,
registration) runs as a subprocess Job; the UI polls Job.current.snapshot().
"""

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from core.config import find_default_config_dir, get_base_path, load_config
from core.dates import get_holidays, get_prev_businessday, is_business_day
from core.inputs import INPUTS, import_files, input_dir, missing, pattern_text
from pipeline import EVENT_PREFIX, PROJECT_ROOT, STEPS

from .state import History, Settings

EXCHANGES = ["NSE", "BSE", "MCX"]
ERROR_LINE = re.compile(r"^(\w+(?:Error|Exception)): (.*)")
SAVED = re.compile(r"Saved (\d+) contracts to")
MAX_LINES = 200_000
IS_WSL = "microsoft" in Path("/proc/version").read_text(errors="ignore").lower() if Path("/proc/version").exists() \
    else False

settings = Settings()
history = History()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def parse_ymd(s: str):
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def latest_business_day() -> date:
    d = date.today()
    return d if is_business_day(d) else get_prev_businessday(d).date()


def next_business_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def to_linux_path(p: str) -> Path:
    """Accept C:\\Users\\me\\Downloads (pasted from Explorer) as well as Linux paths."""
    p = p.strip().strip('"')
    if IS_WSL and re.match(r"^[A-Za-z]:[\\/]", p):
        out = subprocess.run(["wslpath", "-u", p], capture_output=True, text=True).stdout.strip()
        if out:
            return Path(out)
    return Path(os.path.expanduser(p))


def windows_downloads() -> Path:
    """The Windows user's Downloads folder (where the browser saves exchange files); ~/Downloads elsewhere."""
    if IS_WSL:
        try:
            prof = subprocess.run(["cmd.exe", "/c", "echo %USERPROFILE%"], capture_output=True, text=True,
                                  cwd="/mnt/c", timeout=10).stdout.strip()
            p = Path(subprocess.run(["wslpath", "-u", prof], capture_output=True, text=True).stdout.strip()) / "Downloads"
            if p.is_dir():
                return p
        except (OSError, subprocess.TimeoutExpired):
            pass
    return Path.home() / "Downloads"


def open_path(path) -> None:
    """Open a folder in Explorer (WSL) or the desktop file manager."""
    path = str(path)
    if IS_WSL:
        win = subprocess.run(["wslpath", "-w", path], capture_output=True, text=True).stdout.strip()
        subprocess.Popen(["explorer.exe", win or path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 — Explorer
        return
    for opener in ("xdg-open", "open"):
        if shutil.which(opener):
            subprocess.Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return


def config_dir() -> Path:
    return find_default_config_dir()


def update_json(path: Path, mutate) -> None:
    """Load JSON, apply mutate(data), write back keeping <file>.bak."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    mutate(data)
    if path.is_file():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    load_config(reload=True)


DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def describe_cron(expr: str) -> str:
    """'00 6 * * 1-5' -> 'Mon–Fri at 06:00'. Falls back to the raw expression."""
    parts = expr.split()
    if len(parts) != 5:
        return "invalid (needs 5 fields)"
    minute, hour, dom, month, dow = parts
    if not (minute.isdigit() and hour.isdigit()) or dom != "*" or month != "*":
        return expr
    when = f"{int(hour):02d}:{int(minute):02d}"
    if dow == "*":
        return f"Every day at {when}"
    if re.fullmatch(r"\d-\d", dow):
        a, b = map(int, dow.split("-"))
        return f"{DAYS[a]}–{DAYS[b]} at {when}"
    if re.fullmatch(r"\d(,\d)*", dow):
        return f"{', '.join(DAYS[int(x)] for x in dow.split(','))} at {when}"
    return expr


def mask_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    return f"{scheme}://{creds.split(':', 1)[0]}:•••@{host}"


def child_env(**extra) -> dict:
    env = {**os.environ, **extra}
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(PROJECT_ROOT), os.environ.get("PYTHONPATH")]))
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"  # the pipe is read as UTF-8 on every OS
    env.setdefault("PREFECT_LOGGING_COLORS", "false")
    return env


def file_info(f, bd: str) -> dict:
    p = f.path(bd)
    st = p.stat() if p.is_file() else None
    return dict(key=f.key, name=p.name, label=f.label, source=f.source, required=f.required, also=f.names(bd)[1:],
                about=f.about, feeds=f.feeds, pattern=pattern_text(f),
                segments=[STEPS[k].segment for k in f.steps], present=bool(st),
                size=st.st_size if st else 0, mtime=st.st_mtime if st else None)


def friendly_error(kind: str, msg: str) -> str:
    if kind == "FileNotFoundError":
        names = [p.strip().split("/")[-1].split(" (")[0] for p in msg.split("\\n")]
        return "Missing file: " + ", ".join(names)
    return f"{kind}: {msg}"[:240]


# ---------------------------------------------------------------------------
# background job (build / upload / register): one at a time
# ---------------------------------------------------------------------------

class Job:
    current = None

    def __init__(self, kind: str, title: str, cmd: list, env: dict, meta: dict, plan=(), skipped=None):
        self.id = secrets.token_hex(4)
        self.kind, self.title, self.cmd, self.meta = kind, title, cmd, meta
        self.lines = []
        self.steps = {k: dict(key=k, label=f"{STEPS[k].exchange} {STEPS[k].segment}", state="pending")
                      for k in plan}
        for k, why in (skipped or {}).items():
            self.steps[k] = dict(key=k, label=f"{STEPS[k].exchange} {STEPS[k].segment}", state="skipped",
                                 info=why)
        self.code = None
        self.started, self.ended = time.time(), None
        self.running_step = None
        self.proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8", errors="replace",
                                     start_new_session=(os.name == "posix"))
        Job.current = self
        threading.Thread(target=self._pump, daemon=True).start()

    @property
    def running(self) -> bool:
        return self.code is None

    def _pump(self):
        for raw in self.proc.stdout:
            line = raw.rstrip("\n")
            if line.startswith(EVENT_PREFIX):
                self._event(line[len(EVENT_PREFIX):].split())
                continue
            if len(self.lines) < MAX_LINES:
                self.lines.append(line)
            s = self.steps.get(self.running_step)
            if s is not None:
                m = SAVED.search(line)
                if m:
                    s["count"] = int(m.group(1))
                m = ERROR_LINE.match(line.strip())
                if m and "error" not in s:
                    s["error"] = friendly_error(m.group(1), m.group(2))
        self.code = self.proc.wait()
        self.ended = time.time()
        for s in self.steps.values():
            if s["state"] in ("pending", "running"):
                s["state"] = "stopped" if s["state"] == "running" or self.code < 0 else "skipped"
        history.add(self.kind, self.title, self.cmd, self.code, self.ended - self.started,
                    "\n".join(self.lines) + "\n",
                    dict(self.meta, results={k: s["state"] for k, s in self.steps.items()}))

    def _event(self, parts):
        if parts[:1] != ["STEP"] or len(parts) < 3:
            return
        key, what = parts[1], parts[2]
        s = self.steps.setdefault(key, dict(key=key, label=key, state="pending"))
        if what == "START":
            s.update(state="running", started=time.time())
            self.running_step = key
        else:
            s.update(state="ok" if what == "OK" else "fail", seconds=float(parts[3]) if len(parts) > 3 else None)
            if s["state"] == "ok" and "bdate" in self.meta:
                out = STEPS[key].output_path(self.meta["bdate"])
                try:
                    s["output"] = str(out.relative_to(get_base_path()))
                except ValueError:
                    s["output"] = str(out)
                s["path"] = str(out)
            self.running_step = None

    def stop(self):
        if not self.running:
            return
        if os.name != "posix":  # Windows: kill the whole tree (Prefect server, workers) at once
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True)
            return
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        proc = self.proc
        threading.Timer(5, lambda: proc.poll() is None and os.killpg(proc.pid, signal.SIGKILL)).start()

    def snapshot(self, since: int = 0) -> dict:
        now = self.ended or time.time()
        steps = []
        for s in self.steps.values():
            s = dict(s)
            if s["state"] == "running":
                s["seconds"] = time.time() - s.get("started", time.time())
            steps.append(s)
        return dict(id=self.id, kind=self.kind, title=self.title, running=self.running, code=self.code,
                    elapsed=now - self.started, steps=steps, meta=self.meta,
                    lines=self.lines[since:since + 5000], total=len(self.lines))


def start_job(*args, **kw):
    if Job.current and Job.current.running:
        raise ValueError("Another job is still running — wait for it or stop it first.")
    return Job(*args, **kw)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def api_state(q):
    bd = parse_ymd(q.get("date", "")) or latest_business_day()
    shift = int(q.get("shift", "0") or 0)
    if shift > 0:
        bd = next_business_day(bd)
    elif shift < 0:
        bd = get_prev_businessday(bd).date()
    problem = None
    if not is_business_day(bd):
        problem = ("Weekend" if bd.weekday() >= 5 else "Exchange holiday") + \
                  " — masters are only built for business days."
    s = ymd(bd)
    out = dict(date=s, iso=bd.isoformat(), label=f"{bd:%A, %d %B %Y}", is_today=bd == date.today(),
               latest=ymd(latest_business_day()), problem=problem, data_folder=get_base_path(),
               prev_label=f"{get_prev_businessday(bd).date():%a %d %b}", exchanges=[], masters=[],
               job=Job.current.snapshot(10 ** 9) if Job.current else None,
               prefs=dict(settings.get("build", {}), last_scan_path=settings.get("last_scan_path", "")))
    if problem:
        return out
    for ex in EXCHANGES:
        out["exchanges"].append(dict(name=ex, folder=str(input_dir(ex, s)),
                                     files=[file_info(f, s) for f in INPUTS if f.exchange == ex]))
    for k, st in STEPS.items():
        gone, opt = missing(k, s), missing(k, s, required_only=False)
        req = [f for f in INPUTS if k in f.steps and f.required]
        o = st.output_path(s)
        out["masters"].append(dict(
            key=k, exchange=st.exchange, segment=st.segment, ready=not gone,
            missing=[f.name(s) for f in gone], optional_missing=[f.name(s) for f in opt if not f.required],
            have=len(req) - len(gone), need=len(req),
            built=dict(mtime=o.stat().st_mtime, size=o.stat().st_size, path=str(o)) if o.is_file() else None))
    return out


def report_json(r, bd):
    return dict(imported=[dict(exchange=f.exchange, name=f.path(bd).name, label=f.label, origin=o) for f, o in r["imported"]],
                wrong_date=[dict(name=n, expected=f.name(bd), label=f.label) for n, f in r["wrong_date"]],
                ignored=r["ignored"])


def api_import_path(body):
    bd = body["date"]
    p = to_linux_path(body.get("path", ""))
    if not p.exists():
        raise ValueError(f"Folder not found: {p}")
    settings["last_scan_path"] = body.get("path", "")
    settings.save()
    return report_json(import_files([p], bd), bd)


def api_build(body):
    bd = body["date"]
    if not parse_ymd(bd) or not is_business_day(parse_ymd(bd)):
        raise ValueError("Pick a business day first.")
    keys = [k for k in STEPS if k in body.get("steps", [])]
    blocked = {k: "Missing file: " + ", ".join(f.name(bd) for f in missing(k, bd)) for k in keys if missing(k, bd)}
    run = [k for k in keys if k not in blocked]
    if not run:
        raise ValueError("Nothing to build: " + "; ".join(f"{STEPS[k].exchange} {STEPS[k].segment} — {v}"
                                                          for k, v in blocked.items()))
    cmd = [sys.executable, "-u", str(PROJECT_ROOT / "run_all.py"), "-s", ",".join(run), "-d", bd]
    if body.get("stop_on_error"):
        cmd.append("--stop-on-error")
    if not body.get("retry"):
        cmd.append("--no-retry")
    settings["build"] = dict(steps=keys, stop_on_error=bool(body.get("stop_on_error")), retry=bool(body.get("retry")))
    settings.save()
    title = ", ".join(f"{STEPS[k].exchange} {STEPS[k].segment}" for k in run)
    return start_job("pipeline", title, cmd, child_env(), dict(bdate=bd, steps=run), plan=run,
                     skipped=blocked).snapshot()


@lru_cache(maxsize=4)
def load_master(path: str, mtime: float):
    import pandas as pd
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def master_path(p: str) -> Path:
    path = Path(p).resolve()
    if not path.is_file() or not path.suffix == ".csv":
        raise ValueError("File not found")
    return path


def filtered(q):
    path = master_path(q["path"])
    df = load_master(str(path), path.stat().st_mtime)
    view = df
    for col in ("instrument_type", "option_type", "expiry_date", "is_tradeable"):
        v = q.get(col, "")
        if v and col in view:
            view = view[view[col] == v]
    term = q.get("q", "").strip().lower()
    if term:
        mask = None
        for col in ("sutra_symbol", "symbol", "contract_name", "token", "isin"):
            if col in view:
                m = view[col].str.lower().str.contains(term, regex=False)
                mask = m if mask is None else mask | m
        if mask is not None:
            view = view[mask]
    sort = q.get("sort", "")
    if sort in view:
        import pandas as pd
        num = pd.to_numeric(view[sort], errors="coerce")
        key = num if num.notna().mean() > 0.9 else view[sort]
        view = view.loc[key.sort_values(ascending=q.get("desc") != "1", kind="stable").index]
    return df, view


def expiry_key(v):
    try:
        return datetime.strptime(v, "%d %B %Y")
    except ValueError:
        return datetime.max


def api_master(q):
    df, view = filtered(q)
    off, lim = int(q.get("offset", 0)), min(int(q.get("limit", 200)), 1000)
    page = view.iloc[off:off + lim]
    facets = {c: sorted(df[c].unique().tolist(), key=expiry_key if c == "expiry_date" else str)
              for c in ("instrument_type", "option_type", "expiry_date") if c in df}
    by_inst = view["instrument_type"].value_counts().head(8).to_dict() if "instrument_type" in view else {}
    return dict(total=len(df), filtered=len(view), columns=list(df.columns),
                rows=[[int(i), *r] for i, r in zip(page.index, page.itertuples(index=False))],
                facets=facets, by_instrument=by_inst,
                expiries=int(view["expiry_date"].nunique()) if "expiry_date" in view else 0,
                banned=int((view["is_banned"] == "Y").sum()) if "is_banned" in view else 0)


def api_master_row(q):
    path = master_path(q["path"])
    return load_master(str(path), path.stat().st_mtime).loc[int(q["i"])].to_dict()


def api_masters(_q):
    base = Path(get_base_path())
    out = []
    for f in sorted(base.glob("*/common/*/*_contract_master.csv"), key=lambda p: (p.parent.name, p.name), reverse=True):
        parts = f.name.split("_")
        st = f.stat()
        out.append(dict(path=str(f), exchange=parts[0].upper(), segment=parts[1].upper(), bdate=f.parent.name,
                        size=st.st_size, mtime=st.st_mtime))
    return out


def schema_ddl() -> str:
    from db.schema import get_schema_ddl
    return get_schema_ddl()


def api_db_info(_q):
    from db.uploader import get_default_db_url
    url = get_default_db_url(load_config())
    return dict(effective=mask_url(url), source="DATABASE_URL" if os.environ.get("DATABASE_URL") else "config")


def api_db_test(body):
    from db.uploader import get_default_db_url
    from sqlalchemy import create_engine, inspect, text
    url = body.get("url") or get_default_db_url(load_config())
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            version = conn.execute(text("select version()")).scalar().split(",")[0]
            rows = []
            if inspect(conn).has_table("contracts"):
                rows = conn.execute(text("select trade_date, exchange, segment, count(*) from contracts "
                                         "group by 1,2,3 order by 1 desc, 2, 3 limit 60")).fetchall()
        return dict(version=version, rows=[[str(a), b, c, int(d)] for a, b, c, d in rows])
    finally:
        engine.dispose()


def api_db_upload(body):
    cmd = [sys.executable, "-u", "-m", "db.uploader"]
    if body.get("file"):
        cmd += ["-f", body["file"]]
    else:
        cmd += ["-e", body.get("exchange", "all"), "-s", body.get("segment", "all")]
    if body.get("date"):
        cmd += ["-d", body["date"]]
    if str(body.get("chunk", "")).isdigit():
        cmd += ["--chunk-size", str(body["chunk"])]
    if body.get("dry_run"):
        cmd.append("--dry-run")
    if not body.get("create_tables", True):
        cmd.append("--no-create-tables")
    env = child_env(**({"DATABASE_URL": body["url"]} if body.get("url") else {}))  # never on the command line
    title = body.get("file") or f"{body.get('exchange', 'all').upper()} {body.get('segment', 'all').upper()} " \
                                f"{body.get('date') or 'latest'}"
    return start_job("upload", title, cmd, env, dict(bdate=body.get("date", ""), dry_run=bool(body.get("dry_run")))
                     ).snapshot()


def api_settings(_q):
    cfg = load_config(reload=True)
    orch = cfg.get("orchestration", {})
    schedules = orch.get("schedules", {})
    common = config_dir() / "common.json"
    try:
        hol = json.loads(common.read_text(encoding="utf-8")).get("holidays", {})
    except (OSError, ValueError):
        hol = {}
    base = get_base_path()
    return dict(
        data_folder=base, data_folder_exists=os.path.isdir(base), env_override=os.environ.get("BASE_PATH", ""),
        config_folder=str(config_dir()), holidays={ex: sorted(hol.get(ex, [])) for ex in EXCHANGES},
        schedules=[dict(key=k, label=f"{s.exchange} {s.segment}", cron=schedules.get(k, s.default_cron),
                        human=describe_cron(schedules.get(k, s.default_cron)), entrypoint=s.entrypoint)
                   for k, s in STEPS.items()],
        orchestration=dict(work_pool_name=orch.get("work_pool_name", "nse_optflows"),
                           work_queue_name=orch.get("work_queue_name", "prod-queue"), source=orch.get("source", "")),
        config_files=sorted(p.name for p in config_dir().glob("*.json")))


def api_set_data_folder(body):
    if os.environ.get("BASE_PATH"):
        raise ValueError("BASE_PATH environment variable is set; it decides the data folder.")
    p = to_linux_path(body.get("path", ""))
    if not p.is_dir():
        if not body.get("create"):
            raise ValueError(f"Folder does not exist: {p}")
        p.mkdir(parents=True)
    update_json(config_dir() / "common.json", lambda d: d.setdefault("storage", {}).__setitem__("base_path", str(p)))
    return dict(data_folder=get_base_path())


def api_set_holidays(body):
    clean = {ex: sorted({d for d in body.get(ex, []) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)}) for ex in EXCHANGES}
    update_json(config_dir() / "common.json", lambda d: d.__setitem__("holidays", clean))
    return clean


def api_set_schedule(body):
    key, cron = body["key"], " ".join(body.get("cron", "").split())
    if key not in STEPS or len(cron.split()) != 5:
        raise ValueError("A cron expression needs exactly 5 fields, e.g. 00 6 * * 1-5")
    update_json(config_dir() / f"{STEPS[key].exchange.lower()}.json",
                lambda d: d.setdefault("schedules", {}).__setitem__(key, cron))
    return dict(cron=cron, human=describe_cron(cron))


def api_set_orchestration(body):
    def mutate(d):
        o = d.setdefault("orchestration", {})
        for k in ("work_pool_name", "work_queue_name"):
            o[k] = body.get(k, "").strip() or o.get(k, "")
        if body.get("source", "").strip():
            o["source"] = body["source"].strip()
        else:
            o.pop("source", None)
    update_json(config_dir() / "common.json", mutate)
    return {}


def api_register(body):
    keys = [k for k in STEPS if k in body.get("keys", [])] or list(STEPS)
    cmd = [sys.executable, "-u", str(PROJECT_ROOT / "run_all.py"), "-r", "-s", ",".join(keys)]
    return start_job("register", "Prefect deployments", cmd, child_env(), {}).snapshot()


def config_file(name: str) -> Path:
    p = config_dir() / Path(name).name
    if p.suffix != ".json":
        raise ValueError("Only .json config files")
    return p


def api_save_config(body):
    p = config_file(body["name"])
    try:
        json.loads(body["text"])
    except json.JSONDecodeError as e:
        raise ValueError(f"Line {e.lineno}, column {e.colno}: {e.msg}")
    if p.is_file():
        shutil.copy2(p, p.with_suffix(".json.bak"))
    p.write_text(body["text"], encoding="utf-8")
    load_config(reload=True)
    return {}


def api_open(body):
    what = body.get("what")
    if what == "input":
        folder = input_dir(body["exchange"], body["date"])
        folder.mkdir(parents=True, exist_ok=True)
    elif what == "config":
        folder = config_dir()
    elif what == "file":
        folder = Path(body["path"]).parent
    else:
        folder = Path(get_base_path())
        folder.mkdir(parents=True, exist_ok=True)
    open_path(folder)
    return dict(opened=str(folder))


def api_history(_q):
    return [dict(i=i, time=e["time"], kind=e.get("kind"), title=e.get("title", ""), bdate=e.get("bdate", ""),
                 code=e.get("exit_code"), seconds=e.get("seconds", 0), results=e.get("results", {}),
                 dry_run=e.get("dry_run", False), steps=e.get("steps", []))
            for i, e in enumerate(history.entries)]


def api_history_log(q):
    e = history.entries[int(q["i"])]
    p = Path(e.get("log_file", ""))
    return dict(text=p.read_text(encoding="utf-8", errors="replace") if p.is_file() else "(log no longer exists)",
                cmd=" ".join(e.get("cmd", [])))


def api_history_delete(body):
    if body.get("all"):
        while history.entries:
            history.remove(0)
    else:
        history.remove(int(body["i"]))
    return {}


def api_job(q):
    j = Job.current
    if not j or (q.get("id") and q["id"] != j.id):
        return None
    return j.snapshot(int(q.get("since", 0)))


def api_job_stop(_body):
    if Job.current:
        Job.current.stop()
    return {}
