import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { QuizQuestion, SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { memo } from "react"

interface MultipleChoiceProps {
  question: QuizQuestion
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  otherText: string
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
  onOtherTextChange: (text: string, otherOptionValue: string) => void
}

export const MultipleChoice = memo(function MultipleChoice({
  question,
  selectedAnswer,
  otherText,
  onAnswerChange,
  onOtherTextChange,
}: MultipleChoiceProps) {
  let multipleAnswers: string[] = []

  // Find the "other" option value dynamically
  const multiOtherOption = question.options?.find(opt => {
    if (typeof opt === 'string') return false
    return opt.allow_other === true ||
           opt.value.toLowerCase() === 'other' ||
           opt.value.toLowerCase() === 'outro' ||
           opt.value.toLowerCase() === 'outra'
  })
  const multiOtherOptionValue = typeof multiOtherOption === 'object' ? multiOtherOption.value : 'other'

  if (selectedAnswer) {
    if (Array.isArray(selectedAnswer)) {
      multipleAnswers = selectedAnswer
    } else if (typeof selectedAnswer === 'object' && 'options' in selectedAnswer) {
      multipleAnswers = selectedAnswer.options
    }
  }

  return (
    <div className="space-y-3">
      {question.options?.map((option, index) => {
        const optionValue = typeof option === 'string' ? option : option.value
        const optionText = typeof option === 'string' ? option : option.text
        return (
          <div
            key={typeof option === 'string' ? index : option.id}
            className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all"
          >
            <Checkbox
              id={`option-${index}`}
              checked={multipleAnswers.includes(optionValue)}
              onCheckedChange={(checked) => {
                let newAnswers: string[]
                if (checked) {
                  newAnswers = [...multipleAnswers, optionValue]
                } else {
                  newAnswers = multipleAnswers.filter(a => a !== optionValue)
                }

                if (newAnswers.includes(multiOtherOptionValue)) {
                  onAnswerChange({ options: newAnswers, otherText })
                } else {
                  onAnswerChange(newAnswers)
                }
              }}
            />
            <Label
              htmlFor={`option-${index}`}
              className="flex-1 cursor-pointer font-medium"
            >
              {optionText}
            </Label>
          </div>
        )
      })}

      {/* "Outra" option if allowed */}
      {question.allow_other && (
        <div className="space-y-3">
          <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all">
            <Checkbox
              id="option-other"
              checked={multipleAnswers.includes(multiOtherOptionValue)}
              onCheckedChange={(checked) => {
                let newAnswers: string[]
                if (checked) {
                  newAnswers = [...multipleAnswers, multiOtherOptionValue]
                  onAnswerChange({ options: newAnswers, otherText })
                } else {
                  newAnswers = multipleAnswers.filter(a => a !== multiOtherOptionValue)
                  if (newAnswers.length > 0) {
                    onAnswerChange(newAnswers)
                  } else {
                    onAnswerChange([])
                  }
                }
              }}
            />
            <Label
              htmlFor="option-other"
              className="flex-1 cursor-pointer font-medium"
            >
              Outra
            </Label>
          </div>

          {/* Show text input when "Outra" is selected */}
          {multipleAnswers.includes(multiOtherOptionValue) && (
            <Textarea
              value={otherText}
              onChange={(e) => {
                onOtherTextChange(e.target.value, multiOtherOptionValue)
                onAnswerChange({ options: multipleAnswers, otherText: e.target.value })
              }}
              placeholder="Digite sua resposta personalizada..."
              className="min-h-24 resize-none ml-7"
              required
            />
          )}
        </div>
      )}
    </div>
  )
})
