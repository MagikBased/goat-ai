"""Measure sampled Linux RSS of a training command and its worker processes.

The maximum tree RSS is an observed sample, not a guaranteed peak between
samples. The sum of individual high-water marks is not simultaneous usage.
"""

import argparse
import json
import subprocess
from pathlib import Path
from time import perf_counter, sleep


def process_info(pid: int) -> tuple[int, int, int, int] | None:
    """Return parent PID, process start tick, current RSS, and high-water RSS."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        fields = stat[stat.rfind(")") + 2:].split()
        status = Path(f"/proc/{pid}/status").read_text()
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return None
    memory = {}
    for line in status.splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            name, value, *_ = line.split()
            memory[name[:-1]] = int(value)
    return (int(fields[1]), int(fields[19]), memory.get("VmRSS", 0),
            memory.get("VmHWM", 0))


def process_tree(root: int) -> dict[tuple[int, int], tuple[int, int]]:
    """Snapshot the root and recursively reachable descendants in /proc."""
    all_processes = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdecimal():
            info = process_info(int(entry.name))
            if info is not None:
                all_processes[int(entry.name)] = info
    members = {root} if root in all_processes else set()
    changed = True
    while changed:
        previous = len(members)
        members.update(pid for pid, info in all_processes.items() if info[0] in members)
        changed = len(members) != previous
    return {(pid, all_processes[pid][1]): all_processes[pid][2:]
            for pid in members}


def measure(command: list[str], interval: float, stdout: Path) -> dict:
    if not command or interval <= 0:
        raise ValueError("command and positive sample interval are required")
    stdout.parent.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    peaks: dict[tuple[int, int], int] = {}
    sample_count = 0
    maximum_tree_rss = 0
    maximum_parent_rss = 0
    with stdout.open("wb") as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        while True:
            snapshot = process_tree(process.pid)
            sample_count += 1
            maximum_tree_rss = max(maximum_tree_rss,
                                   sum(current for current, _ in snapshot.values()))
            maximum_parent_rss = max(maximum_parent_rss,
                                     next((current for (pid, _), (current, _) in
                                           snapshot.items() if pid == process.pid), 0))
            for identity, (_, high_water) in snapshot.items():
                peaks[identity] = max(peaks.get(identity, 0), high_water)
            if process.poll() is not None:
                break
            sleep(interval)
    workers = sorted(({"pid": pid, "start_tick": tick, "peak_rss_kb": peak}
                      for (pid, tick), peak in peaks.items() if pid != process.pid),
                     key=lambda entry: (entry["pid"], entry["start_tick"]))
    return {"command": command, "exit_code": process.returncode,
            "wall_seconds": perf_counter() - started,
            "sample_interval_seconds": interval, "samples": sample_count,
            "max_sampled_tree_rss_kb": maximum_tree_rss,
            "max_sampled_parent_rss_kb": maximum_parent_rss,
            "sum_worker_peak_rss_kb": sum(item["peak_rss_kb"] for item in workers),
            "workers_observed": len(workers), "worker_processes": workers,
            "stdout": str(stdout)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stdout", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    report = measure(command, args.interval, args.stdout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ("command", "worker_processes")}, indent=2))
    if report["exit_code"]:
        raise SystemExit(report["exit_code"])


if __name__ == "__main__":
    main()
