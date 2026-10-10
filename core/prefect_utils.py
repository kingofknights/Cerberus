"""
Prefect utility functions and hooks for flow/task orchestration and notifications.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from prefect.runtime import flow_run, task_run
from prefect.client.schemas.schedules import CronSchedule


def task_retries(n: int) -> int:
    """Task retry count; 0 when CONTRACT_DOWNLOADER_NO_RETRY=1 (interactive fail-fast runs).

    Read at import time, so the env var must be set before flows are imported.
    """
    return 0 if os.environ.get("CONTRACT_DOWNLOADER_NO_RETRY") == "1" else n


def task_name_gen() -> str:
    """
    Generate dynamic task run name combining date, flow name, and task name.
    
    Returns:
        str: Generated name in 'YYYY-MM-DD-flow_name-task_name' format
    """
    try:
        task_name = task_run.task_name
        flow_name = flow_run.flow_name
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{today}-{flow_name}-{task_name}"
    except Exception:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{today}-task"


def unified_notifier(notification_type: str = "both") -> Callable:
    """
    State hook for Prefect tasks and flows to notify on state changes (failure, completion, crash, etc.).
    
    Args:
        notification_type: Notification channel/type ('slack', 'email', 'both', 'log')
        
    Returns:
        Callable: Prefect state change hook function
    """
    def hook(task_or_flow: Any, run: Any, state: Any) -> None:
        run_name = getattr(run, "name", str(run))
        state_name = getattr(state, "name", str(state))
        state_msg = getattr(state, "message", "")
        print(f"[Notifier] Type={notification_type} | Run={run_name} | State={state_name} | Message={state_msg}")

    return hook


def deploy_flow(
    flow_name: str,
    cron: str,
    parameters: Optional[Dict[str, Any]] = None,
    work_pool: str = "nse_optflows",
    queue_name: str = "prod-queue",
    timezone: str = "Asia/Kolkata",
) -> Any:
    """
    Helper function to standardize deployment of Prefect flows.
    """
    from prefect import flow
    from prettytable import PrettyTable

    current_user = os.environ.get("USER", "unknown")
    flow_basename = os.path.basename(flow_name).replace(".py", "")
    project_name = os.path.basename(os.path.dirname(flow_name))

    schedule = CronSchedule(cron=cron, timezone=timezone) if cron else None

    table = PrettyTable()
    table.add_row(["USER", current_user], divider=True)
    table.add_row(["PROJECT", project_name], divider=True)
    table.add_row(["FLOW", flow_basename], divider=True)
    table.add_row(["WORK POOL", work_pool], divider=True)
    table.add_row(["QUEUE", queue_name], divider=True)
    table.add_row(["SCHEDULE", cron], divider=True)
    print(table.get_string(header=False))

    flow_obj = flow.from_source(
        source=str(Path(__file__).resolve().parent.parent),
        entrypoint=f"./flows/{flow_basename}.py:{flow_basename}",
    )

    schedules = [schedule] if schedule else []
    deployment = flow_obj.deploy(
        name=f"{project_name}-{flow_basename}",
        version="1",
        tags=[project_name],
        work_pool_name=work_pool,
        work_queue_name=queue_name,
        schedules=schedules,
        parameters=parameters or {},
        build=False,
        push=False,
    )
    return deployment
