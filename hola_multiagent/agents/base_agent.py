from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Mapping

import pandas as pd


@dataclass
class AgentResponse:
    agent_name: str
    output: str
    confidence: float
    alerts: list[str] = field(default_factory=list)
    tables: list[pd.DataFrame] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def has_alerts(self) -> bool:
        return bool(self.alerts)


class BaseAgent(ABC):
    name: str
    role_description: str
    system_prompt: str

    @abstractmethod
    def run(
        self,
        query: str,
        context: dict,
        dataframes: Mapping[str, pd.DataFrame],
    ) -> AgentResponse:
        raise NotImplementedError

    def _empty_response(
        self,
        output: str,
        confidence: float = 0.0,
        alerts: list[str] | None = None,
        assumptions: list[str] | None = None,
    ) -> AgentResponse:
        return AgentResponse(
            agent_name=self.name,
            output=output,
            confidence=confidence,
            alerts=alerts or [],
            assumptions=assumptions or [],
        )

    def _get_dataframe(
        self,
        dataframes: Mapping[str, pd.DataFrame],
        name: str,
    ) -> pd.DataFrame:
        dataframe = dataframes.get(name)
        if dataframe is None:
            return pd.DataFrame()
        return dataframe
