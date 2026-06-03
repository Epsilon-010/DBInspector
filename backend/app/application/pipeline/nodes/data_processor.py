from __future__ import annotations

import asyncio

import pandas as pd

from app.application.pipeline.state import PipelineState


class DataProcessorNode:
    name = "data_processor"

    async def run(self, state: PipelineState) -> PipelineState:
        if state.result is None:
            raise RuntimeError("DataProcessorNode invoked without a query result")

        rows = await asyncio.to_thread(_clean_with_pandas, state.result.to_dict_rows())
        return state.with_(processed_rows=rows)


def _clean_with_pandas(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")
