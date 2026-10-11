"""Run the requested Blender script to completion, flush, and preserve its exit code."""

import os
import runpy
import sys
import traceback

code = 1
try:
    runpy.run_path(os.environ["REGISTRY_CHECKED_SCRIPT"], run_name="__main__")
    code = 0
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
except BaseException:
    traceback.print_exc()
finally:
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
