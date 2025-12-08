import { Textarea } from "@/components/ui/textarea"
import type { SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { memo } from "react"

interface TextQuestionProps {
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
}

export const TextQuestion = memo(function TextQuestion({
  selectedAnswer,
  onAnswerChange,
}: TextQuestionProps) {
  return (
    <Textarea
      value={selectedAnswer as string || ""}
      onChange={(e) => onAnswerChange(e.target.value)}
      placeholder="Digite sua resposta aqui..."
      className="min-h-32 resize-none"
    />
  )
})
