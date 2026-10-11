"""The offline guide stays reachable alongside the frontend and version endpoint."""

from fastapi.testclient import TestClient

import backend.api as web
from backend import __version__
from backend.config import Config


def test_guide_and_health_routes_take_precedence_over_frontend(tmp_path, monkeypatch):
    guide = tmp_path / "docs/guide"
    guide.mkdir(parents=True)
    (guide / "index.html").write_text("<h1>Offline pipeline</h1>")
    (guide / "en.html").write_text("<h1>English pipeline</h1>")
    frontend = tmp_path / "frontend/dist"
    frontend.mkdir(parents=True)
    (frontend / "index.html").write_text("<h1>Frontend</h1>")
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "palette.yaml").write_text("colors: {gray: '#888888'}\n")
    monkeypatch.setattr(web, "ROOT", tmp_path)
    monkeypatch.setattr(web, "FRONTEND_DIST", frontend)
    app = web.create_app(Config(registry_dir=registry, build_dir=tmp_path / "build",
                                db_path=tmp_path / "var/index.sqlite"))
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {
            "status": "ok", "version": __version__, "registry_available": True,
            "frontend_available": True,
        }
        assert "Frontend" in client.get("/").text
        assert "Offline pipeline" in client.get("/guide/").text
        assert "English pipeline" in client.get("/guide/en.html").text
        assert client.get("/guide/missing.html").status_code == 404
