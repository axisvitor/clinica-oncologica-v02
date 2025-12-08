import { Circle } from "lucide-react"
import { memo } from "react"

interface QuizHeaderProps {
  patientName: string
  templateName: string
}

export const QuizHeader = memo(function QuizHeader({ patientName, templateName }: QuizHeaderProps) {
  return (
    <div className="text-center space-y-4">
      <div className="inline-flex items-center gap-2 bg-primary/10 text-primary px-4 py-2 rounded-full text-sm font-medium">
        <Circle className="w-4 h-4 fill-current" />
        Quiz Mensal - {patientName}
      </div>
      <h1 className="text-2xl font-bold">{templateName}</h1>
    </div>
  )
})
