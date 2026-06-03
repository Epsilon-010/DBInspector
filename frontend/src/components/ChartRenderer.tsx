import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { ChartSpec } from '@/domain/types'

interface ChartRendererProps {
  spec: ChartSpec
  rows: Array<Record<string, unknown>>
  height?: number
}

const PALETTE = ['#7c5cff', '#5b8def', '#34d399', '#fbbf24', '#f87171', '#22d3ee', '#a78bfa']

const TOOLTIP_STYLE = {
  background: '#11172d',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: '0.5rem',
  color: '#e6e9f5',
} as const

const AXIS_STYLE = { fill: '#9aa3c4', fontSize: 11 } as const

export function ChartRenderer({ spec, rows, height = 320 }: ChartRendererProps) {
  if (spec.type === 'table' || !spec.x || !spec.y || rows.length === 0) {
    return null
  }

  const data = normalizeRows(rows, spec)

  switch (spec.type) {
    case 'bar':
      return (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey={spec.x} tick={AXIS_STYLE} />
            <YAxis tick={AXIS_STYLE} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey={spec.y} fill={PALETTE[0]} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )
    case 'line':
      return (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey={spec.x} tick={AXIS_STYLE} />
            <YAxis tick={AXIS_STYLE} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Line type="monotone" dataKey={spec.y} stroke={PALETTE[0]} strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      )
    case 'scatter':
      return (
        <ResponsiveContainer width="100%" height={height}>
          <ScatterChart margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey={spec.x} tick={AXIS_STYLE} />
            <YAxis dataKey={spec.y} tick={AXIS_STYLE} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ strokeDasharray: '3 3' }} />
            <Scatter data={data} fill={PALETTE[0]} />
          </ScatterChart>
        </ResponsiveContainer>
      )
    case 'pie':
      return (
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ color: '#9aa3c4', fontSize: 12 }} />
            <Pie
              data={data}
              dataKey={spec.y}
              nameKey={spec.x}
              outerRadius={120}
              label={(entry: { name?: string | number }) => String(entry.name ?? '')}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      )
  }
}

function normalizeRows(
  rows: Array<Record<string, unknown>>,
  spec: ChartSpec,
): Array<Record<string, unknown>> {
  if (!spec.y) return rows
  return rows.map((row) => {
    const numericY = Number(row[spec.y as string])
    return {
      ...row,
      [spec.y as string]: Number.isFinite(numericY) ? numericY : row[spec.y as string],
    }
  })
}
