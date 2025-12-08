/**
 * MessagesList Component - Main messages display with virtual scrolling
 *
 * Orchestrates message display with:
 * - Virtual scrolling for performance
 * - Date-based grouping
 * - Message retry functionality
 * - Auto-scroll to bottom
 */

import React from 'react'
import { MessageSquare, Inbox } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'
import { apiClient } from '@/lib/api-client'
import { getErrorMessage } from '@/lib/utils/type-guards'
import { VariableSizeList, ListChildComponentProps } from 'react-window'
import AutoSizer from 'react-virtualized-auto-sizer'

import { useMessageGroups, useVirtualScroll } from './hooks'
import { MessageRow } from './components/MessageRow'
import { MessageSkeleton } from './components/MessageSkeleton'
import type { Message } from './hooks/useMessageGroups'
import type { MessageRowData } from './components/MessageRow'

interface MessagesListProps {
  messages: Message[]
  isLoading: boolean
  patientName?: string
}

/**
 * Main component for displaying message history with virtual scrolling
 */
export function MessagesList({
  messages,
  isLoading,
  patientName
}: MessagesListProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // Message retry mutation
  const retryMutation = useMutation({
    mutationFn: (messageId: string) => apiClient.messages.retry(messageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] })
      toast({
        title: 'Mensagem reenviada',
        description: 'A mensagem foi colocada na fila para ser reenviada.',
      })
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao reenviar',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Group messages by date with separators
  const items = useMessageGroups(messages)

  // Virtual scroll management
  const { listRef, getItemSize } = useVirtualScroll({
    items,
    autoScrollToBottom: true
  })

  // Row data for virtual scrolling
  const itemData: MessageRowData = {
    items,
    retryMutation
  }

  // Wrapper component to adapt react-window's ListChildComponentProps to MessageRow's props
  const Row = ({ index, style, data }: ListChildComponentProps<MessageRowData>) => (
    <MessageRow
      index={index}
      style={style}
      items={data.items}
      retryMutation={data.retryMutation}
    />
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <MessageSquare className="h-5 w-5" />
          <span>Mensagens</span>
          {patientName && (
            <span className="text-sm font-normal text-gray-500">
              - {patientName}
            </span>
          )}
        </CardTitle>
        <CardDescription>
          Histórico de conversas com o paciente
        </CardDescription>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <MessageSkeleton />
        ) : messages.length === 0 ? (
          <div className="text-center py-8">
            <Inbox className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p className="text-gray-500">Nenhuma mensagem encontrada</p>
            <p className="text-sm text-gray-400">
              As mensagens aparecerão aqui quando enviadas
            </p>
          </div>
        ) : (
          <div className="h-[350px] md:h-[400px] w-full">
            <AutoSizer>
              {({ height, width }) => (
                <VariableSizeList
                  ref={listRef}
                  height={height}
                  width={width}
                  itemCount={items.length}
                  itemSize={getItemSize}
                  itemData={itemData}
                  overscanCount={5}
                >
                  {Row}
                </VariableSizeList>
              )}
            </AutoSizer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
