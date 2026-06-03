import { graphqlRequest } from '@/api/client'

const RUN_QUERY = /* GraphQL */ `
  mutation RunQuery($question: String!, $conversationId: ID) {
    runQuery(question: $question, conversationId: $conversationId) {
      requestId
    }
  }
`

interface RunQueryData {
  runQuery: { requestId: string }
}

interface RunQueryArgs {
  question: string
  conversationId?: string | null
}

export async function runQuery({ question, conversationId }: RunQueryArgs): Promise<string> {
  const data = await graphqlRequest<RunQueryData, { question: string; conversationId: string | null }>({
    query: RUN_QUERY,
    variables: { question, conversationId: conversationId ?? null },
    operationName: 'RunQuery',
  })
  return data.runQuery.requestId
}
