#!/usr/bin/env python3
"""
Phoenix Contract Master builder - command line runner.

Builds any combination of the contract masters defined in pipeline.py from exchange files
that were downloaded by hand into <base_path>/<exchange>/source/<YYYYMMDD>/ (see core/inputs.py).
For the graphical interface run:  python3 -m gui   (or ./run_gui.sh)
"""

import os
import sys
import time
from pathlib import Path

import click
from prettytable import PrettyTable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import find_default_config_path, load_config
from core.dates import generate_business_dates
from core.inputs import missing
from pipeline import GROUP_HELP, GROUPS, STEPS, RunArgs, register_deployments, resolve_steps, run_steps


def _steps_epilog() -> str:
    lines = ["\b", "Groups:"]
    lines += [f"  {g:<13} {GROUP_HELP[g]}" for g in GROUPS]
    lines += ["", "\b", "Single steps:"]
    lines += [f"  {k:<13} {s.label}" for k, s in STEPS.items()]
    lines += ["", "\b", "Examples:",
              "  run_all.py                          # every master for today",
              "  run_all.py -s nse -d 20260828       # NSE CM + FO",
              "  run_all.py -s nse_fo,bse_fo         # two masters only",
              "  run_all.py -d 20260801:20260828     # date range",
              "  run_all.py --dry-run                # show plan only",
              "  run_all.py -r                       # register Prefect deployments"]
    return "\n".join(lines)


@click.command(epilog=_steps_epilog(),
               help="🦅 Phoenix Contract Master builder (NSE / BSE / MCX) from manually downloaded files.")
@click.option("-d", "--bdate", default="", help="YYYYMMDD, YYYY-MM-DD, A:B range or A,B list [default: today]")
@click.option("-s", "--step", "steps", multiple=True, default=["all"], show_default=True,
              help="Group or step key; repeat or comma-separate for several")
@click.option("-c", "--config", default="", help="Config directory or JSON file")
@click.option("--stop-on-error", is_flag=True, help="Stop at the first failing step")
@click.option("--no-retry", is_flag=True, help="Fail fast: disable Prefect task retries (masters retry 6x20min)")
@click.option("--dry-run", is_flag=True, help="Print plan and exit")
@click.option("-r", "--register", is_flag=True, help="Register selected steps as Prefect deployments")
def main(bdate, steps, config, stop_on_error, no_retry, dry_run, register):
    if no_retry:
        os.environ["CONTRACT_DOWNLOADER_NO_RETRY"] = "1"  # before flows are imported
    cfg = load_config(config or None, reload=True)

    try:
        keys = resolve_steps(steps)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="-s/--step")

    dates = generate_business_dates(bdate, use_holidays="NSE", weekdays_only=True)
    header = PrettyTable(header=False, align="l")
    header.title = "Contract Master builder"
    header.add_rows([
        ["Config", str(config or find_default_config_path())],
        ["Data folder", cfg.get("storage", {}).get("base_path", "")],
        ["Business date(s)", ", ".join(dates) or "none (all holidays/weekends)"],
        ["Steps", ", ".join(keys)],
        ["Mode", "REGISTER" if register else "DRY RUN" if dry_run else "EXECUTE"],
        ["Task retries", "off (fail fast)" if no_retry else "on"],
    ])
    for d in dates:
        for k in keys:
            gone = missing(k, d)
            if gone:
                header.add_row([f"⚠ {d} {k} missing", ", ".join(str(f.path(d)) for f in gone)])
    print(header)

    if register:
        table = PrettyTable(["Step", "Cron", "Status"])
        table.add_rows(register_deployments(cfg, keys))
        print(table)
        return
    if dry_run:
        print("\nDry run: nothing executed.")
        return

    t0 = time.time()
    results = run_steps(keys, RunArgs(bdate, config), stop_on_error)

    summary = PrettyTable(["Step", "Status", "Duration", "Error"])
    summary.align["Error"] = "l"
    for key, (ok, dt, err) in results.items():
        summary.add_row([STEPS[key].label, "SUCCESS" if ok else "FAILED", f"{dt:.2f}s", err[:80]])
    print("\nPIPELINE SUMMARY")
    print(summary)
    print(f"Total runtime: {time.time() - t0:.2f}s")
    sys.exit(0 if all(ok for ok, _, _ in results.values()) else 1)


if __name__ == "__main__":
    main()
