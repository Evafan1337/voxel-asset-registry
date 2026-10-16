"""Moving parts never cross: builder/motion_clearance.py over the whole `work` loop of built GLBs.

The steam engine's conrod used to swing through its slide bars and guide standard, the piston ran into
the front cover and the valve chest, and the crankshaft showed through the eccentric strap. Only the
joints listed here may touch; the models are skipped while they are not built."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from backend.config import load_config
from backend.planner import Planner
from backend.store import Store

ROOT = Path(__file__).resolve().parent.parent
STEAM_JOINTS = ["crosshead:conrod", "conrod:crank", "crosshead:cylinder",           # pins, piston rod in its gland
                "cylinder:valve_spindle", "eccentric_rod:valve_spindle"]
CASES = [("mx_steam_engine", v, STEAM_JOINTS) for v in ("v001", "v002", "v003")]


@pytest.fixture(scope="module")
def planner() -> Planner:
    cfg = load_config()
    return Planner(Store(cfg.registry_dir), cfg)


@pytest.mark.skipif(shutil.which("blender") is None, reason="Blender executable unavailable")
@pytest.mark.parametrize("entity,vid,joints", CASES)
def test_moving_parts_keep_clear(planner: Planner, entity: str, vid: str, joints: list[str]) -> None:
    glb = load_config().build_dir / planner.resolve("components", entity, vid).hash / "model.glb"
    if not glb.exists():
        pytest.skip(f"{entity} {vid} is not built")
    cmd = ["blender", "-b", "--factory-startup", "--python-exit-code", "1",
           "-P", str(ROOT / "builder/motion_clearance.py"), "--", str(glb), "--skip", "exhaust,drain"]
    for joint in joints:
        cmd += ["--joint", joint]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    report = [line for line in run.stdout.splitlines() if "CROSS" in line or "motion_clearance:" in line]
    assert run.returncode == 0, "\n".join(report) or run.stdout[-2000:] + run.stderr[-2000:]
