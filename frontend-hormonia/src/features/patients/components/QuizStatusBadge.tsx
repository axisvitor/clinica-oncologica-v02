/**
 * QuizStatusBadge Component
 * Displays quiz status with interactive send/resend functionality
 */

import React from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { MonthlyQuizStatus } from '../MonthlyQuizStatus'
import { useMonthlyQuizStatus, useResendQuizLink } from '@/hooks/useMonthlyQuizStatus'

interface QuizStatusBadgeProps {
  patientId: string
  patientName: string
  onSendQuiz: (patient: { id: string; name: string }) => void
  isResending?: boolean
  compact?: boolean
}

export const QuizStatusBadge: React.FC<QuizStatusBadgeProps> = ({
  patientId,
  patientName,
  onSendQuiz,
  isResending = false,
  compact = false
}) => {
  const { data: quizStatus, isLoading } = useMonthlyQuizStatus(patientId)
  const resendQuizLinkMutation = useResendQuizLink()

  if (isLoading) {
    return (
      <Badge
        variant="outline"
        className={`animate-pulse ${compact ? 'text-xs' : ''}`}
      >
        Carregando...
      </Badge>
    )
  }

  if (!quizStatus || quizStatus.status === 'not_sent') {
    return (
      <Button
        variant="ghost"
        size="sm"
        className={compact ? 'h-7 text-xs' : ''}
        onClick={(e) => {
          e.stopPropagation()
          onSendQuiz({ id: patientId, name: patientName })
        }}
      >
        <Send className={`${compact ? 'h-3 w-3' : 'h-4 w-4'} mr-1`} />
        Enviar
      </Button>
    )
  }

  return (
    <MonthlyQuizStatus
      status={quizStatus.status}
      {...(quizStatus.last_sent && { lastSent: quizStatus.last_sent })}
      {...(quizStatus.access_date && { accessDate: quizStatus.access_date })}
      {...(quizStatus.completion_date && { completionDate: quizStatus.completion_date })}
      {...(quizStatus.expires_at && { expiresAt: quizStatus.expires_at })}
      {...(quizStatus.session_id && {
        onResend: () => resendQuizLinkMutation.mutate(quizStatus.session_id!)
      })}
      isResending={isResending}
    />
  )
}
