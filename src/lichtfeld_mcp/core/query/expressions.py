from __future__ import annotations

from dataclasses import dataclass

from lichtfeld_mcp.core.gaussian import RGBColor

from .operators import COLOR_SIMILAR, AND, BETWEEN, NOT, OR, ComparisonOperator, LogicalOperator


class QueryExpression:
    def __and__(self, other: "QueryExpression") -> "LogicalExpression":
        return LogicalExpression(operator=AND, left=self, right=other)

    def __or__(self, other: "QueryExpression") -> "LogicalExpression":
        return LogicalExpression(operator=OR, left=self, right=other)

    def __invert__(self) -> "NotExpression":
        return NotExpression(operator=NOT, operand=self)


@dataclass(frozen=True, slots=True)
class ComparisonExpression(QueryExpression):
    field_name: str
    operator: ComparisonOperator
    value: float


@dataclass(frozen=True, slots=True)
class RangeExpression(QueryExpression):
    field_name: str
    operator: ComparisonOperator = BETWEEN
    lower: float | None = None
    upper: float | None = None


@dataclass(frozen=True, slots=True)
class ColorSimilarityExpression(QueryExpression):
    color: RGBColor
    tolerance: int
    operator: ComparisonOperator = COLOR_SIMILAR


@dataclass(frozen=True, slots=True)
class LogicalExpression(QueryExpression):
    operator: LogicalOperator
    left: QueryExpression
    right: QueryExpression


@dataclass(frozen=True, slots=True)
class NotExpression(QueryExpression):
    operator: LogicalOperator
    operand: QueryExpression
