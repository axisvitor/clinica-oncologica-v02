import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import type { SingleAnswer, MultipleAnswer } from "@/types/quiz"
import { memo } from "react"

interface YesNoProps {
  selectedAnswer: SingleAnswer | MultipleAnswer | null
  onAnswerChange: (value: SingleAnswer | MultipleAnswer) => void
}

export const YesNo = memo(function YesNo({
  selectedAnswer,
  onAnswerChange,
}: YesNoProps) {
  return (
    <RadioGroup
      value={selectedAnswer as string || ""}
      onValueChange={onAnswerChange}
      className="space-y-3"
    >
      <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer">
        <RadioGroupItem value="yes" id="yes" />
        <Label htmlFor="yes" className="flex-1 cursor-pointer font-medium">
          Sim
        </Label>
      </div>
      <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer">
        <RadioGroupItem value="no" id="no" />
        <Label htmlFor="no" className="flex-1 cursor-pointer font-medium">
          Não
        </Label>
      </div>
    </RadioGroup>
  )
})
