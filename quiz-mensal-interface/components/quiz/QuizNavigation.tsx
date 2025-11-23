import { Button } from "@/components/ui/button"
import { ArrowLeft, ArrowRight, Send, Loader2 } from "lucide-react"
import { memo } from "react"

interface QuizNavigationProps {
  currentQuestionIndex: number
  isLastQuestion: boolean
  isSubmitting: boolean
  hasAnswer: boolean
  onPrevious: () => void
  onSubmit: () => void
}

export const QuizNavigation = memo(function QuizNavigation({
  currentQuestionIndex,
  isLastQuestion,
  isSubmitting,
  hasAnswer,
  onPrevious,
  onSubmit,
}: QuizNavigationProps) {
  return (
    <div className="flex gap-3 pt-4 border-t">
      {currentQuestionIndex > 0 && (
        <Button
          onClick={onPrevious}
          variant="outline"
          disabled={isSubmitting}
          className="flex-1"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Voltar
        </Button>
      )}

      <Button
        onClick={onSubmit}
        disabled={!hasAnswer || isSubmitting}
        className="flex-1"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Enviando...
          </>
        ) : isLastQuestion ? (
          <>
            <Send className="w-4 h-4 mr-2" />
            Finalizar Quiz
          </>
        ) : (
          <>
            Próxima
            <ArrowRight className="w-4 h-4 ml-2" />
          </>
        )}
      </Button>
    </div>
  )
})
