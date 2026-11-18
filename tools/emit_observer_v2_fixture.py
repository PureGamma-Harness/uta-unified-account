"""Data-only bounded child for a separately authorized adapter probe.

One small complete frame is flushed, then this process remains alive until its
parent's fresh private release marker exists. No observer, SQL or service runs.
"""
import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.managed_observer_transport import input_frame
from tools.probe_observer_v2_adapters import ADAPTER_PARENT, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-marker', type=Path, required=True)
    args = parser.parse_args()
    path = args.release_marker
    if (not path.is_absolute() or path.name != 'release.json' or path.parent.name != 'control'
            or path.parents[2] != ADAPTER_PARENT or path.exists() or path.is_symlink()):
        return 2
    def audit(event, _args):
        if event in {'sqlite3.connect', 'subprocess.Popen', 'os.fork', 'os.posix_spawn', 'socket.connect',
                     'socket.bind', 'os.kill', 'os.killpg', 'ctypes.dlopen'}:
            raise RuntimeError('data_emitter_forbidden_effect:' + event)
    sys.addaudithook(audit)
    sys.stdout.buffer.write(input_frame(report(1), 1)); sys.stdout.buffer.flush()
    deadline = time.monotonic() + 3
    while not path.exists():
        if time.monotonic() >= deadline: return 2
        time.sleep(.002)
    for index in (2, 3, 4):
        sys.stdout.buffer.write(input_frame(report(index), index)); sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
