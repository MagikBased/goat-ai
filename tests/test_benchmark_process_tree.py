"""The PPO memory probe measures the command process and spawned workers."""

import os
import sys

import pytest

from scripts.benchmark_process_tree import measure, process_info, process_tree


@pytest.mark.skipif(not os.path.isdir("/proc/self"), reason="Linux /proc required")
def test_process_tree_includes_current_process():
    info = process_info(os.getpid())
    assert info is not None
    assert info[2] > 0
    assert info[3] >= info[2]
    assert any(pid == os.getpid() for pid, _ in process_tree(os.getpid()))


@pytest.mark.skipif(not os.path.isdir("/proc/self"), reason="Linux /proc required")
def test_measure_captures_spawned_worker_and_exit_code(tmp_path):
    worker = "import time; data=bytearray(4_000_000); time.sleep(.25)"
    parent = ("import subprocess,sys; subprocess.run([sys.executable,'-c',"
              f"{worker!r}]); print('finished')")
    output = tmp_path / "run.stdout"
    report = measure([sys.executable, "-c", parent], 0.02, output)
    assert report["exit_code"] == 0
    assert report["workers_observed"] >= 1
    assert report["max_sampled_tree_rss_kb"] > report["max_sampled_parent_rss_kb"]
    assert report["sum_worker_peak_rss_kb"] > 0
    assert output.read_text().strip() == "finished"
