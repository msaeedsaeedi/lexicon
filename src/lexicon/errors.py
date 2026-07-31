from __future__ import annotations


class PipelineError(ValueError):
    """An expected, actionable pipeline failure."""

    code = "pipeline.error"

    def diagnostic(self) -> str:
        return f"{self.code}: {self}"
