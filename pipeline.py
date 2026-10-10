"""
Pipeline step registry: the single source of truth for what can run.

Both the CLI (run_all.py) and the GUI (gui/) read STEPS/GROUPS from here, so a new
flow is added in exactly one place.
"""

import importlib
import os
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Lines starting with this marker are machine-readable progress events for the GUI.
EVENT_PREFIX = "@@"


@dataclass(frozen=True)
class RunArgs:
    bdate: str = ""
    config_path: str = ""


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    exchange: str  # NSE / BSE / MCX
    segment: str  # CM / FO
    module: str
    func: str
    default_cron: str = "00 6 * * 1-5"
    date_param: str = "business_date_str"  # name of the business-date parameter of the flow

    @property
    def cron_key(self) -> str:
        return self.key

    def output_path(self, bdate: str) -> Path:
        from core.config import get_storage_config
        return Path(get_storage_config(self.exchange)[f"{self.segment.lower()}_master_output"].format(bdate=bdate))

    @property
    def entrypoint(self) -> str:
        return f"./{self.module.replace('.', '/')}.py:{self.func}"

    def run(self, args: RunArgs) -> None:
        flow_fn = getattr(importlib.import_module(self.module), self.func)
        flow_fn(**{self.date_param: args.bdate})


STEPS: Dict[str, Step] = {s.key: s for s in [
    Step("nse_cm", "NSE CM contract master", "NSE", "CM", "flows.nse_cm_master_flow", "nse_cm_contract_master_generation"),
    Step("nse_fo", "NSE FO contract master", "NSE", "FO", "flows.nse_fo_master_flow", "nse_fo_contract_master_generation"),
    Step("bse_cm", "BSE CM contract master", "BSE", "CM", "flows.bse_cm_master_flow", "bse_cm_contract_master_generation"),
    Step("bse_fo", "BSE FO contract master", "BSE", "FO", "flows.bse_fo_master_flow", "bse_fo_contract_master_generation"),
    Step("mcx_fo", "MCX FO contract master", "MCX", "FO", "flows.mcx_fo_master_flow", "mcx_fo_contract_master_generation"),
]}


def _where(**match) -> List[str]:
    return [k for k, s in STEPS.items() if all(getattr(s, f) == v for f, v in match.items())]


GROUPS: Dict[str, List[str]] = {
    "all": list(STEPS),
    "master": list(STEPS),  # old name for "all", kept for existing cron lines / scripts
    "nse": _where(exchange="NSE"),
    "bse": _where(exchange="BSE"),
    "mcx": _where(exchange="MCX"),
    "cm": _where(segment="CM"),
    "fo": _where(segment="FO"),
}

GROUP_HELP = {
    "all": "Build every contract master",
    "master": "Same as 'all'",
    "nse": "NSE CM + FO masters",
    "bse": "BSE CM + FO masters",
    "mcx": "MCX FO master",
    "cm": "All CM (cash) masters",
    "fo": "All FO (derivatives) masters",
}


def resolve_steps(selection: Iterable[str]) -> List[str]:
    """Expand group names / step keys (comma-separated allowed) into ordered step keys."""
    wanted = set()
    for token in selection:
        for name in str(token).lower().replace(" ", "").split(","):
            if not name:
                continue
            if name in GROUPS:
                wanted.update(GROUPS[name])
            elif name in STEPS:
                wanted.add(name)
            else:
                valid = ", ".join([*GROUPS, *STEPS])
                raise ValueError(f"Unknown step '{name}'. Valid: {valid}")
    return [k for k in STEPS if k in wanted]


def emit(*parts) -> None:
    print(EVENT_PREFIX + " ".join(str(p) for p in parts), flush=True)


def run_steps(keys: List[str], args: RunArgs, stop_on_error: bool = False) -> Dict[str, tuple]:
    """Run steps in order. Returns {key: (ok, seconds, error)}."""
    results: Dict[str, tuple] = {}
    emit("PLAN", ",".join(keys))
    for key in keys:
        step = STEPS[key]
        print("\n" + "=" * 80 + f"\n>>> {step.label}  [{key}]\n" + "=" * 80, flush=True)
        emit("STEP", key, "START")
        t0 = time.time()
        try:
            step.run(args)
            ok, err = True, ""
        except Exception as exc:  # one failing exchange must not stop the others
            traceback.print_exc()
            ok, err = False, str(exc)
        dt = time.time() - t0
        results[key] = (ok, dt, err)
        emit("STEP", key, "OK" if ok else "FAIL", f"{dt:.2f}")
        if not ok and stop_on_error:
            break
    return results


def register_deployments(cfg: dict, keys: Optional[List[str]] = None) -> List[tuple]:
    """Register Prefect deployments for the given steps. Returns [(name, cron, status)]."""
    from prefect import flow
    from prefect.client.schemas.schedules import CronSchedule

    orch = cfg.get("orchestration", {})
    schedules = orch.get("schedules", {})
    source = orch.get("source", f"/home/{os.environ.get('USER', 'unknown')}/devopts/")
    rows = []
    for key in keys or list(STEPS):
        step = STEPS[key]
        cron = schedules.get(step.cron_key, step.default_cron)
        try:
            flow.from_source(source=source, entrypoint=step.entrypoint).deploy(
                name=f"contractDownloader-{key}",
                version="1.0",
                tags=["contractDownloader", step.exchange.lower()],
                work_pool_name=orch.get("work_pool_name", "nse_optflows"),
                work_queue_name=orch.get("work_queue_name", "prod-queue"),
                schedules=[CronSchedule(cron=cron, timezone="Asia/Kolkata")],
                parameters={step.date_param: ""},  # empty = "today" at run time
                build=False,
                push=False,
            )
            rows.append((key, cron, "REGISTERED"))
        except Exception as exc:
            rows.append((key, cron, f"ERROR: {exc}"))
    return rows


if __name__ == "__main__":
    assert resolve_steps(["all"]) == list(STEPS)
    assert resolve_steps(["mcx_fo,nse"]) == ["nse_cm", "nse_fo", "mcx_fo"]
    assert resolve_steps(["bse"]) == ["bse_cm", "bse_fo"]
    assert resolve_steps(["fo"]) == ["nse_fo", "bse_fo", "mcx_fo"]
    try:
        resolve_steps(["nope"])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert STEPS["nse_cm"].entrypoint == "./flows/nse_cm_master_flow.py:nse_cm_contract_master_generation"
    print("pipeline self-check OK")
