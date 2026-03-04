import React from 'react'
import { Send, CheckCircle, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { QuizLinkStatus } from '@/features/quiz/QuizLinkStatus'
import type { QuizHistoryEntry } from '@/lib/api-client/monthly-quiz'

interface QuizStatusData {
  status: string
  session_id?: string
  expires_at?: string
  sent_at?: string
  last_sent?: string
  access_date?: string
}

interface PatientQuizSectionProps {
  patientId: string
  quizStatus: QuizStatusData | null | undefined
  quizHistory: QuizHistoryEntry[]
  quizHistoryLoading: boolean
  completedQuizCount: number
  quizCompletionRate: number
  onSendQuiz: () => void
  onResendQuiz: (sessionId: string) => void
  onCancelQuiz: (sessionId: string) => void
}

export function PatientQuizSection({
  patientId,
  quizStatus,
  quizHistory,
  quizHistoryLoading,
  completedQuizCount,
  quizCompletionRate,
  onSendQuiz,
  onResendQuiz,
  onCancelQuiz,
}: PatientQuizSectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Quiz Mensal</span>
          {quizStatus && patientId && (
            <QuizLinkStatus
              patientId={patientId}
              {...(quizStatus.last_sent && { lastSent: new Date(quizStatus.last_sent) })}
              {...(quizStatus.access_date && { lastResponse: new Date(quizStatus.access_date) })}
              linkStatus={quizStatus.status}
              {...(quizStatus.expires_at && { expiresAt: new Date(quizStatus.expires_at) })}
            />
          )}
        </CardTitle>
        <CardDescription>Gerencie o questionário mensal de bem-estar</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Action Buttons */}
          <div className="flex items-center space-x-2">
            <Button onClick={onSendQuiz} disabled={quizStatus?.status === 'active'}>
              <Send className="mr-2 h-4 w-4" />
              {quizStatus?.status === 'active' ? 'Link Ativo' : 'Enviar Link'}
            </Button>
            {quizStatus?.status === 'active' && quizStatus?.session_id && (
              <>
                <Button
                  variant="outline"
                  onClick={() => quizStatus.session_id && onResendQuiz(quizStatus.session_id)}
                >
                  Reenviar
                </Button>
                <Button
                  variant="outline"
                  onClick={() => quizStatus.session_id && onCancelQuiz(quizStatus.session_id)}
                >
                  Cancelar
                </Button>
              </>
            )}
          </div>

          {/* Metrics */}
          {quizHistory && quizHistory.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
              <div className="p-4 border rounded-lg">
                <div className="flex items-center space-x-2">
                  <Send className="h-5 w-5 text-blue-600" />
                  <span className="text-sm text-gray-600">Total Enviados</span>
                </div>
                <p className="text-2xl font-bold mt-2">{quizHistory.length}</p>
              </div>
              <div className="p-4 border rounded-lg">
                <div className="flex items-center space-x-2">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  <span className="text-sm text-gray-600">Completados</span>
                </div>
                <p className="text-2xl font-bold mt-2">{completedQuizCount}</p>
              </div>
              <div className="p-4 border rounded-lg">
                <div className="flex items-center space-x-2">
                  <TrendingUp className="h-5 w-5 text-purple-600" />
                  <span className="text-sm text-gray-600">Taxa de Conclusão</span>
                </div>
                <p className="text-2xl font-bold mt-2">{quizCompletionRate}%</p>
              </div>
            </div>
          )}

          {/* History */}
          {quizHistoryLoading ? (
            <div className="flex items-center justify-center py-4">
              <LoadingSpinner />
            </div>
          ) : (
            quizHistory &&
            quizHistory.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-gray-900 mb-2">Histórico</h4>
                <div className="space-y-2">
                  {quizHistory.slice(0, 5).map((entry: QuizHistoryEntry) => (
                    <div
                      key={entry.id}
                      className="flex items-center justify-between p-2 border rounded"
                    >
                      <div>
                        <p className="text-sm font-medium">{entry.quiz_template_name}</p>
                        <p className="text-xs text-gray-500">
                          {entry.sent_at && new Date(entry.sent_at).toLocaleDateString('pt-BR')}
                        </p>
                      </div>
                      {patientId && (
                        <QuizLinkStatus
                          patientId={patientId}
                          {...(entry.sent_at && { lastSent: new Date(entry.sent_at) })}
                          {...(entry.accessed_at && { lastResponse: new Date(entry.accessed_at) })}
                          linkStatus={entry.status}
                          {...(entry.expires_at && { expiresAt: new Date(entry.expires_at) })}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          )}
        </div>
      </CardContent>
    </Card>
  )
}
