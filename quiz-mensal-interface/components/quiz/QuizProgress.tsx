import { Progress } from '@/components/ui/progress'
import { memo } from 'react'

interface QuizProgressProps {
  currentQuestion: number
  totalQuestions: number
  progress: number
}

export const QuizProgress = memo(function QuizProgress({
  currentQuestion,
  totalQuestions,
  progress,
}: QuizProgressProps) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>
          Pergunta {currentQuestion} de {totalQuestions}
        </span>
        <span>{Math.round(progress)}%</span>
      </div>
      <Progress value={progress} className="h-2" />
    </div>
  )
})
