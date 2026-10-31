"""The LLM layer: provider Protocol, mock/live/record/replay, the response
store, the shared runner and the task modules.

`tasks` is imported on demand (`from overheard.llm import tasks`) so merely
importing this package stays cheap.
"""

from overheard.llm.cache import ResponseStore
from overheard.llm.provider import LLMProvider, Provenance, Task, build_provider, input_hash
from overheard.llm.run import LLMResult, run_task

__all__ = ["LLMProvider", "LLMResult", "Provenance", "ResponseStore", "Task", "build_provider", "input_hash", "run_task"]
