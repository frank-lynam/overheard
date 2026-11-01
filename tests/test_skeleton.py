import subprocess
import sys
import zipfile
from pathlib import Path

import httpx

from overheard import __version__
from overheard.app import create_app
from overheard.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit:
        pass
    assert __version__ in capsys.readouterr().out


async def test_health_and_shell(seeded):
    from overheard.config import Settings

    transport = httpx.ASGITransport(app=create_app(Settings(db_path=seeded[0])))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = (await client.get("/api/health")).json()
        assert health == {"ok": True, "version": __version__, "llm_mode": "mock"}
        page = await client.get("/")
        assert page.status_code == 200 and "Impossible without AI" in page.text
        assert (await client.get("/js/main.js")).status_code == 200
        deck = await client.get("/present")
        assert deck.status_code == 200 and "presenter" in deck.text
        assert (await client.get("/js/present.js")).status_code == 200
        assert (await client.get("/css/present.css")).status_code == 200


def test_wheel_has_the_front_end(tmp_path):
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path), str(ROOT)],
                   check=True, capture_output=True)
    names = zipfile.ZipFile(next(tmp_path.glob("*.whl"))).namelist()
    for needed in ("index.html", "css/app.css", "js/main.js", "js/core/store.js",
                   "present.html", "css/present.css", "js/present.js"):
        assert f"overheard/static/{needed}" in names
    assert "overheard/data/seed_today.json" in names
