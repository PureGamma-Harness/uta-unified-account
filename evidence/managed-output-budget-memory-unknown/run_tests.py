"""Use the same pure batch with new outputs; preserve all previous raw logs."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('source_binding_commands',
    ROOT/'evidence/managed-output-budget-source-binding/run_tests.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MODULE.OUT = Path(__file__).resolve().parent

if __name__ == '__main__':
    MODULE.main()
