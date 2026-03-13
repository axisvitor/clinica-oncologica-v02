import type { ApiClientCore } from './core'
import type {
  Message,
  MessageListFilters,
  SendMessageRequest,
  BulkMessageRequest,
  BulkMessageResponse,
  ConversationResponse,
  PaginatedResponse,
  MessageResponse,
} from './types'

export interface MessagesListOptions extends MessageListFilters {
  page?: number
  size?: number
  cursor?: string
  limit?: number
}

export interface MessagesApi {
  list: (options?: MessagesListOptions) => Promise<PaginatedResponse<Message>>
  get: (messageId: string) => Promise<Message>
  send: (data: SendMessageRequest) => Promise<Message>
  markAsRead: (messageId: string) => Promise<MessageResponse>
  delete: (messageId: string) => Promise<MessageResponse>
  getConversation: (patientId: string) => Promise<ConversationResponse>
  sendBulk: (data: BulkMessageRequest) => Promise<BulkMessageResponse>
  retry: (messageId: string) => Promise<Message>
}

export function createMessagesApi(client: ApiClientCore): MessagesApi {
  return {
    list: async (options: MessagesListOptions = {}) => {
      const { size, cursor, limit, ...filters } = options
      const effLimit = limit ?? size ?? 20
      const params: Record<string, string | number | boolean> = {
        limit: effLimit,
        ...(cursor ? { cursor } : {}),
        ...filters,
      }
      const res = await client.get<PaginatedResponse<Message>>('/api/v2/messages', params)
      const items = Array.isArray(res?.data) ? res.data : (res?.items ?? [])
      return {
        data: items,
        items,
        total: res?.total ?? 0,
        has_more: res?.has_more,
        next_cursor: res?.next_cursor,
      }
    },

    get: (messageId: string) => client.get<Message>(`/api/v2/messages/${messageId}`),

    send: (data: SendMessageRequest) => client.post<Message>('/api/v2/messages', data),

    markAsRead: (messageId: string) => client.patch<MessageResponse>(`/api/v2/messages/${messageId}/read`),

    delete: (messageId: string) => client.delete<MessageResponse>(`/api/v2/messages/${messageId}`),

    getConversation: (patientId: string) =>
      client.get<ConversationResponse>(`/api/v2/messages/conversations/${patientId}`),

    sendBulk: (data: BulkMessageRequest) =>
      client.post<BulkMessageResponse>('/api/v2/messages/bulk', data),

    retry: (messageId: string) => client.post<Message>(`/api/v2/messages/${messageId}/retry`),
  }
}
