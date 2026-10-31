"""The one response store: live LLM responses kept as JSON files.

Keyed by (task, input hash, model). `live` reads and writes it as a cache,
`record` writes it, `replay` only reads it and never touches the network.
No separate SQLite cache.
"""

import json
import os
import tempfile
from pathlib import Path


class ResponseStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def _file(self, task_name: str, key: str, model: str) -> Path:
        safe_model = model.replace("/", "_")
        return self.path / f"{task_name}-{key[:16]}-{safe_model}.json"

    def get(self, task_name: str, key: str, model: str) -> str | None:
        f = self._file(task_name, key, model)
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))["output"]
        except (json.JSONDecodeError, KeyError):
            return None

    def put(self, task_name: str, key: str, model: str, output: str) -> None:
        f = self._file(task_name, key, model)
        fd, tmp = tempfile.mkstemp(dir=self.path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"task": task_name, "key": key, "model": model, "output": output}, fh, ensure_ascii=False)
            os.replace(tmp, f)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
