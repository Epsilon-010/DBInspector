interface DataTableProps {
  columns: string[]
  rows: Array<Record<string, unknown>>
  maxHeight?: string
}

export function DataTable({ columns, rows, maxHeight = '24rem' }: DataTableProps) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-ink-faint italic">
        La consulta no devolvió filas.
      </p>
    )
  }
  return (
    <div className="overflow-auto rounded-xl border border-white/5" style={{ maxHeight }}>
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 bg-bg-subtle/95 backdrop-blur">
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                className="px-3 py-2 text-left font-medium text-ink-dim text-xs uppercase tracking-wider"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map((row, idx) => (
            <tr key={idx} className="hover:bg-white/[0.02]">
              {columns.map((col) => (
                <td key={col} className="px-3 py-2 text-ink font-mono text-xs">
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
