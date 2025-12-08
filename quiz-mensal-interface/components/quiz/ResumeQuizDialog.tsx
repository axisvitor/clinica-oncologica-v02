"use client"

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Progress } from "@/components/ui/progress"
import { PlayCircle, RefreshCcw } from "lucide-react"
import type { QuizProgress } from "@/lib/quiz-progress-storage"

interface ResumeQuizDialogProps {
  open: boolean
  progress: QuizProgress | null
  onResume: () => void
  onStartFresh: () => void
}

export function ResumeQuizDialog({ open, progress, onResume, onStartFresh }: ResumeQuizDialogProps) {
  if (!progress) return null

  const progressPercentage = ((progress.currentQuestionIndex + 1) / progress.totalQuestions) * 100
  const answeredQuestions = Object.keys(progress.answers).length
  const lastSavedDate = new Date(progress.lastSaved)
  const timeAgo = getTimeAgo(progress.lastSaved)

  return (
    <AlertDialog open={open}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <PlayCircle className="w-5 h-5 text-primary" />
            Continuar Questionário?
          </AlertDialogTitle>
          <AlertDialogDescription className="space-y-4 pt-4">
            <p className="text-base">
              Encontramos um questionário em andamento. Você gostaria de continuar de onde parou?
            </p>

            <div className="bg-muted/50 rounded-lg p-4 space-y-3">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Progresso</p>
                <div className="space-y-2">
                  <Progress value={progressPercentage} className="h-2" />
                  <p className="text-xs text-muted-foreground">
                    {answeredQuestions} de {progress.totalQuestions} perguntas respondidas ({Math.round(progressPercentage)}%)
                  </p>
                </div>
              </div>

              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Paciente</p>
                <p className="text-sm text-muted-foreground">{progress.patientName}</p>
              </div>

              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Último salvamento</p>
                <p className="text-sm text-muted-foreground">
                  {timeAgo} ({lastSavedDate.toLocaleString("pt-BR")})
                </p>
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-col sm:flex-row gap-2">
          <AlertDialogCancel onClick={onStartFresh} className="w-full sm:w-auto">
            <RefreshCcw className="w-4 h-4 mr-2" />
            Começar do Início
          </AlertDialogCancel>
          <AlertDialogAction onClick={onResume} className="w-full sm:w-auto">
            <PlayCircle className="w-4 h-4 mr-2" />
            Continuar de onde parei
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function getTimeAgo(timestamp: number): string {
  const now = Date.now()
  const diff = now - timestamp

  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return "agora mesmo"
  if (minutes < 60) return `há ${minutes} minuto${minutes > 1 ? 's' : ''}`
  if (hours < 24) return `há ${hours} hora${hours > 1 ? 's' : ''}`
  return `há ${days} dia${days > 1 ? 's' : ''}`
}
