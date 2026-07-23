from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class RuntimeMetrics:
    started_at: float = field(default_factory=time.time)
    counters: Counter[str] = field(default_factory=Counter)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def render_prometheus(self) -> str:
        lines = [
            "# HELP scooter_bot_uptime_seconds Bot process uptime in seconds",
            "# TYPE scooter_bot_uptime_seconds gauge",
            f"scooter_bot_uptime_seconds {int(time.time() - self.started_at)}",
        ]
        for name, value in sorted(self.counters.items()):
            metric = "scooter_bot_" + name.replace("-", "_").replace(".", "_")
            lines.extend([f"# TYPE {metric} counter", f"{metric} {value}"])
        return "\n".join(lines) + "\n"


metrics = RuntimeMetrics()
