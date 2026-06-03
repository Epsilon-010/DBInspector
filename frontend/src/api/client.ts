import axios, { AxiosError, type AxiosInstance } from 'axios'

import { env } from '@/lib/env'

export const http: AxiosInstance = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

export interface GraphQLPayload<TVars = Record<string, unknown>> {
  query: string
  variables?: TVars
  operationName?: string
}

export interface GraphQLResponse<T> {
  data?: T
  errors?: Array<{ message: string; path?: Array<string | number> }>
}

export class GraphQLClientError extends Error {
  readonly cause?: unknown
  constructor(message: string, cause?: unknown) {
    super(message)
    this.name = 'GraphQLClientError'
    this.cause = cause
  }
}

export function toErrorMessage(err: unknown): string {
  if (err instanceof GraphQLClientError) return err.message
  if (err instanceof Error) return err.message
  return String(err)
}

export async function graphqlRequest<TData, TVars = Record<string, unknown>>(
  payload: GraphQLPayload<TVars>,
): Promise<TData> {
  try {
    const { data } = await http.post<GraphQLResponse<TData>>('/graphql', payload)
    if (data.errors?.length) {
      throw new GraphQLClientError(
        data.errors.map((e: { message: string }) => e.message).join('; '),
      )
    }
    if (data.data === undefined) {
      throw new GraphQLClientError('GraphQL response had no data')
    }
    return data.data
  } catch (err) {
    if (err instanceof GraphQLClientError) throw err
    if (err instanceof AxiosError) {
      const status = err.response?.status
      const detail = err.response?.data ?? err.message
      throw new GraphQLClientError(
        `HTTP ${status ?? '?'} from /graphql: ${
          typeof detail === 'string' ? detail : JSON.stringify(detail)
        }`,
        err,
      )
    }
    throw new GraphQLClientError('Unexpected error calling /graphql', err)
  }
}
