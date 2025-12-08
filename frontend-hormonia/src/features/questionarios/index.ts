/**
 * Questionarios Components
 *
 * This module exports all components related to questionnaire management.
 * The original QuestionariosPage.tsx (1,039 lines) has been refactored into
 * smaller, maintainable components following React best practices.
 *
 * @module questionarios
 */

export { QuestionariosHeader } from './QuestionariosHeader'
export { QuestionariosStats } from './QuestionariosStats'
export { QuestionariosFilters } from './QuestionariosFilters'
export type { QuestionariosFiltersConfig } from './QuestionariosFilters'
export { QuestionarioCard } from './QuestionarioCard'
export type { QuizTemplate } from '@/types/api'
export { QuestionariosGrid } from './QuestionariosGrid'
export { QuestionForm } from './QuestionForm'
export type { QuizQuestion, QuestionOption } from '@/types/api'
export { CreateQuestionarioModal } from './CreateQuestionarioModal'
export type { CreateQuizFormData } from './CreateQuestionarioModal'
export { EditQuestionarioModal } from './EditQuestionarioModal'
