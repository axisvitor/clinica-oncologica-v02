import type { QuizQuestion, SingleAnswer, MultipleAnswer } from '@/types/quiz'
import { memo, useCallback } from 'react'

interface ScaleProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
}

export const Scale = memo(function Scale({ question, selectedAnswer, onAnswerChange }: ScaleProps) {
  const scaleMin = question.min_value || 0
  const scaleMax = question.max_value || 10
  const scaleValues = Array.from({ length: scaleMax - scaleMin + 1 }, (_, i) => scaleMin + i)

  const currentValue = selectedAnswer ? parseInt(selectedAnswer as string, 10) : scaleMin

  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onAnswerChange(e.target.value)
    },
    [onAnswerChange],
  )

  return (
    <div className="space-y-4">
      {/* Mobile: Slider with value display */}
      <div className="sm:hidden space-y-3">
        <div className="flex justify-center">
          <span className="text-4xl font-bold text-primary">{currentValue}</span>
        </div>
        <input
          id={`question-${question.id}-scale`}
          name={`question-${question.id}-scale`}
          type="range"
          min={scaleMin}
          max={scaleMax}
          value={currentValue}
          onChange={handleSliderChange}
          className="w-full h-3 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
        />
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>{scaleMin}</span>
          <span>{scaleMax}</span>
        </div>
      </div>

      {/* Desktop: Button row */}
      <div className="hidden sm:flex justify-between items-center gap-2">
        {scaleValues.map((value) => (
          <button
            key={value}
            onClick={() => onAnswerChange(value.toString())}
            className={`
              flex-1 h-12 rounded-lg border-2 transition-all font-semibold
              ${
                selectedAnswer === value.toString()
                  ? 'border-primary bg-primary text-primary-foreground shadow-lg scale-110'
                  : 'border-border hover:border-primary/50 hover:bg-primary/5'
              }
            `}
          >
            {value}
          </button>
        ))}
      </div>

      {/* Desktop: Labels */}
      <div className="hidden sm:flex justify-between text-sm text-muted-foreground">
        <span>Minimo ({scaleMin})</span>
        <span>Maximo ({scaleMax})</span>
      </div>
    </div>
  )
})
