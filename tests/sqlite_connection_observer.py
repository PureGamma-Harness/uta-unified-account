"""Observational tracing of real initialized SQLite handles in one test thread."""
from contextlib import contextmanager
import sqlite3
import sys


@contextmanager
def trace_new_sqlite_connections(statements):
    """Attach only after sqlite3.connect has actually returned.

    The audit handle event arrives too early to call Connection methods. A
    temporary profile observer sees the real C return and attaches to that same
    handle. Neither connect, Database nor any financial method is substituted.
    The audit callback becomes inert at exit and holds no connection afterward.
    """
    enabled, pending = [True], []
    previous = sys.getprofile()
    def audit(event, arguments):
        if enabled[0] and event == "sqlite3.connect/handle":
            pending.append(arguments[0])
    def profile(frame, event, argument):
        if enabled[0] and argument is sqlite3.connect:
            if event == "c_return" and pending:
                pending.pop().set_trace_callback(statements.append)
            elif event == "c_exception":
                pending.clear()
        if previous is not None:
            previous(frame, event, argument)
    sys.addaudithook(audit)
    sys.setprofile(profile)
    try:
        yield
    finally:
        enabled[0] = False
        sys.setprofile(previous)
        pending.clear()
