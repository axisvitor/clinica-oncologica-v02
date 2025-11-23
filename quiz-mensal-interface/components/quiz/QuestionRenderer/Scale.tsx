import type { QuizQuestion, SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { memo } from "react"

interface ScaleProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
}

export const Scale = memo(function Scale({
  question,
  selectedAnswer,
  onAnswerChange,
}: ScaleProps) {
  const scaleMin = question.min_value || 0
  const scaleMax = question.max_value || 10
  const scaleValues = Array.from({ length: scaleMax - scaleMin + 1 }, (_, i) => scaleMin + i)

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center gap-2">
        {scaleValues.map((value) => (
          <button
            key={value}
            onClick={() => onAnswerChange(value.toString())}
            className={`
              flex-1 h-12 rounded-lg border-2 transition-all font-semibold
              ${selectedAnswer === value.toString()
                ? "border-primary bg-primary text-primary-foreground shadow-lg scale-110"
                : "border-border hover:border-primary/50 hover:bg-primary/5"
              }
            `}
          >
            {value}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>Mínimo ({scaleMin})</span>
        <span>Máximo ({scaleMax})</span>
      </div>
    </div>
  )
})
