/**
 * Templates Feature Exports
 *
 * Central export point for template management components and hooks.
 */

// Main page
export { default as TemplateManagementPage } from './TemplateManagementPage'
export type { TemplateFilter } from './TemplateManagementPage'

// Flow components
export { FlowTemplateList } from './flows/FlowTemplateList'
export { FlowTemplateCard } from './flows/FlowTemplateCard'
export { FlowDesignerDialog } from './flows/FlowDesignerDialog'
export { useFlowTemplates } from './flows/hooks/useFlowTemplates'

// Quiz components
export { QuizTemplateList } from './quiz/QuizTemplateList'
export { QuizEditorDialog } from './quiz/QuizEditorDialog'
export { QuestionEditor } from './quiz/QuestionEditor'
export { useQuizTemplates } from './quiz/hooks/useQuizTemplates'

// Utils
export { convertTemplateToDesign, convertDesignToTemplate } from './utils/templateConverters'
export { TemplateCardSkeleton } from './utils/TemplateCardSkeleton'
