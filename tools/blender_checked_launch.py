#!/usr/bin/python3
"""Task-local headless launcher that avoids Blender's slow native teardown.

Use as Config.blender_bin without changing the project's config.yaml. It wraps
the requested Python script, preserves its exit status and flushes output.
No geometry, export or validation steps are skipped. REGISTRY_NATIVE_BLENDER
can select the native executable; this workstation's snap binary is default.
"""

import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
for flag in ("-P", "--python"):
    if flag in arguments:
        index = arguments.index(flag) + 1
        os.environ["REGISTRY_CHECKED_SCRIPT"] = str(Path(arguments[index]).resolve())
        arguments[index] = str(Path(__file__).with_name("blender_checked_exit.py"))
        break
native = os.environ.get("REGISTRY_NATIVE_BLENDER", "/snap/blender/current/blender")
os.execv(native, [native, *arguments])
