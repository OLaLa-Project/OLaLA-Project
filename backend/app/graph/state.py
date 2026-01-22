from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class GraphState:
    trace_id: str
    data: Dict[str, Any]
