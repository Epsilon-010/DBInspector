import { graphqlRequest } from '@/api/client'
import { parseFinalReport, REPORT_GRAPHQL_FIELDS, type RawFinalReport } from '@/api/reportShape'
import type { FinalReport } from '@/domain/types'

const REPORT_QUERY = /* GraphQL */ `
  query Report($requestId: ID!) {
    report(requestId: $requestId) {
      ${REPORT_GRAPHQL_FIELDS}
    }
  }
`

interface ReportData {
  report: RawFinalReport | null
}

export async function fetchReport(requestId: string): Promise<FinalReport | null> {
  const data = await graphqlRequest<ReportData, { requestId: string }>({
    query: REPORT_QUERY,
    variables: { requestId },
    operationName: 'Report',
  })
  return data.report ? parseFinalReport(data.report) : null
}
