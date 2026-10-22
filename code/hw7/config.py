"""Fixed configuration required for DATA 260 HW7."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HomeworkConfig:
    sid4: int = 7838
    port: int = 8638
    prefix: str = "s7838"
    seed: int = 7838
    verify_seed: int = 267838
    domain_id: int = 6
    model: str = "qwen2:7b"
    hardware: str = "MacBook Pro (Apple M4 Pro, 48 GB unified memory)"

    def as_dict(self) -> dict[str, int | str]:
        return asdict(self)


CONFIG = HomeworkConfig()
