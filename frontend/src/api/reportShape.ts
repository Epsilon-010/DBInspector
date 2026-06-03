import type { FinalReport } from '@/domain/types'

export interface RawFinalReport {
  question: string
  sql: string
  result: {
    columns: string[]
    rowCount: number
    truncated: boolean
    rowsJson: string
  }
  analysis: {
    summary: string
    chart: {
      type: string | null
      x: string | null
      y: string | null
      series: string | null
      title: string
    }
  }
}

export const REPORT_GRAPHQL_FIELDS = /* GraphQL */ `
  question
  sql
  result {
    columns
    rowCount
    truncated
    rowsJson
  }
  analysis {
    summary
    chart {
      type
      x
      y
      series
      title
    }
  }
`

type ChartType = FinalReport['analysis']['chart']['type']

export function parseFinalReport(raw: RawFinalReport): FinalReport {
  return {
    question: raw.question,
    sql: raw.sql,
    result: {
      columns: raw.result.columns,
      rowCount: raw.result.rowCount,
      truncated: raw.result.truncated,
      rows: JSON.parse(raw.result.rowsJson) as Array<Record<string, unknown>>,
    },
    analysis: {
      summary: raw.analysis.summary,
      chart: {
        type: (raw.analysis.chart.type ?? 'table') as ChartType,
        x: raw.analysis.chart.x,
        y: raw.analysis.chart.y,
        series: raw.analysis.chart.series,
        title: raw.analysis.chart.title,
      },
    },
  }
}
