"""JSON policy and metadata-only measurement of owned observer output trees."""

import os
from pathlib import Path
import re
import stat

GIB = 1024**3
DEFAULT_OUTPUT_BUDGET_BYTES = 6 * GIB
MIN_OUTPUT_BUDGET_BYTES = GIB


def output_budget_bytes(plan):
    """Resolve bytes without mutating the plan or accepting bool as an integer."""
    if type(plan) is not dict or type(plan.get('observer')) is not dict:
        raise ValueError('observer_output_budget_plan_invalid')
    observer = plan['observer']
    if 'output_budget_bytes' not in observer:
        return DEFAULT_OUTPUT_BUDGET_BYTES
    value = observer['output_budget_bytes']
    if type(value) is not int or not MIN_OUTPUT_BUDGET_BYTES <= value <= DEFAULT_OUTPUT_BUDGET_BYTES:
        raise ValueError('observer_output_budget_bytes_invalid')
    return value


def explicit_output_budget(plan):
    """An explicit field opts into the full output-tree measurement/drain policy."""
    output_budget_bytes(plan)
    return 'output_budget_bytes' in plan['observer']


def measured_output_bytes(control, observer):
    """Count full output trees, excluding only validated private clone directories.

    Directory FDs anchor nofollow metadata traversal of owned output, never DB
    contents. This observation is not an atomic snapshot or a peak-disk quota.
    Missing/unreadable entries and symlinks fail closed, including inside clones.
    """
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC

    def walk(fd, location, excluded=False):
        if len(location) > 32:
            raise ValueError('observer_output_directory_depth_unknown')
        total = 0
        with os.scandir(fd) as entries:
            for entry in entries:
                details = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(details.st_mode):
                    child = os.open(entry.name, flags, dir_fd=fd)
                    try:
                        opened = os.fstat(child)
                        if (opened.st_dev, opened.st_ino) != (details.st_dev, details.st_ino):
                            raise ValueError('observer_output_directory_identity_changed')
                        is_private = location == ('observer',) and entry.name == 'private-audit'
                        is_clone = (location == ('observer', 'private-audit')
                                    and re.fullmatch(r'private-full-clone-[a-z0-9_]{8}', entry.name) is not None)
                        if (is_private or is_clone) and (opened.st_uid != os.geteuid() or stat.S_IMODE(opened.st_mode) != 0o700):
                            raise ValueError('observer_output_private_clone_identity_invalid')
                        total += walk(child, (*location, entry.name), excluded or is_clone)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(details.st_mode):
                    if not excluded:
                        total += details.st_size
                else:
                    raise ValueError('observer_output_symlink_or_special_file')
        return total

    total = 0
    for name, path in (('control', control), ('observer', observer)):
        fd = os.open(Path(path), flags)
        try:
            total += walk(fd, (name,))
        finally:
            os.close(fd)
    return total
