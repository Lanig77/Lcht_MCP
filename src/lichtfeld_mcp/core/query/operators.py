from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComparisonOperator:
    name: str


@dataclass(frozen=True, slots=True)
class LogicalOperator:
    name: str


GT = ComparisonOperator("gt")
GTE = ComparisonOperator("gte")
LT = ComparisonOperator("lt")
LTE = ComparisonOperator("lte")
BETWEEN = ComparisonOperator("between")
COLOR_SIMILAR = ComparisonOperator("color_similar")

AND = LogicalOperator("and")
OR = LogicalOperator("or")
NOT = LogicalOperator("not")
