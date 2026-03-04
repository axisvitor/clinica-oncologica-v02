/**
 * Test Fixtures Factory
 * Provides reusable test data builders
 */
import type { QuizSession, QuizQuestion } from '@/types/quiz'

// Option type matching QuizQuestion.options
type QuizOption = { id?: string; value: string; text: string; allow_other?: boolean }

/**
 * Quiz Question Builder
 */
export class QuizQuestionBuilder {
  private question: QuizQuestion = {
    id: `q-${Date.now()}`,
    text: 'Default Question',
    type: 'text',
    required: true,
    allow_other: false,
  }

  withId(id: string): this {
    this.question.id = id
    return this
  }

  withText(text: string): this {
    this.question.text = text
    return this
  }

  withType(type: QuizQuestion['type']): this {
    this.question.type = type
    return this
  }

  withOptions(options: QuizOption[]): this {
    this.question.options = options
    return this
  }

  withScale(min: number, max: number): this {
    this.question.type = 'scale'
    this.question.min_value = min
    this.question.max_value = max
    return this
  }

  required(required: boolean = true): this {
    this.question.required = required
    return this
  }

  allowOther(allow: boolean = true): this {
    this.question.allow_other = allow
    return this
  }

  build(): QuizQuestion {
    return { ...this.question }
  }
}

/**
 * Quiz Session Builder
 */
export class QuizSessionBuilder {
  private session: QuizSession = {
    id: `id-${Date.now()}`,
    quiz_session_id: `session-${Date.now()}`,
    patient_id: 'patient-123',
    patient_name: 'Test Patient',
    template_id: 'template-123',
    template_name: 'Test Template',
    status: 'in_progress',
    current_question_index: 0,
    expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    questions: [new QuizQuestionBuilder().withId('q1').withText('Test Question').build()],
  }

  withId(id: string): this {
    this.session.id = id
    return this
  }

  withSessionId(id: string): this {
    this.session.quiz_session_id = id
    return this
  }

  withPatient(id: string, name: string): this {
    this.session.patient_id = id
    this.session.patient_name = name
    return this
  }

  withTemplate(id: string, name: string): this {
    this.session.template_id = id
    this.session.template_name = name
    return this
  }

  withStatus(status: string): this {
    this.session.status = status
    return this
  }

  withCurrentQuestion(index: number): this {
    this.session.current_question_index = index
    return this
  }

  withQuestions(questions: QuizQuestion[]): this {
    this.session.questions = questions
    return this
  }

  withExpiry(date: Date): this {
    this.session.expires_at = date.toISOString()
    return this
  }

  expired(): this {
    this.session.expires_at = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
    return this
  }

  build(): QuizSession {
    return { ...this.session }
  }
}

/**
 * Preset Fixtures
 */
export const fixtures = {
  // Single choice question with "Outra" option
  singleChoiceWithOther: () =>
    new QuizQuestionBuilder()
      .withId('q-single-other')
      .withType('single_choice')
      .withText('Qual é o principal sintoma?')
      .withOptions([
        { id: 'opt1', value: 'headache', text: 'Dor de cabeça' },
        { id: 'opt2', value: 'nausea', text: 'Náusea' },
        { id: 'opt3', value: 'fatigue', text: 'Fadiga' },
      ])
      .allowOther(true)
      .build(),

  // Multiple choice question with "Outra" option
  multipleChoiceWithOther: () =>
    new QuizQuestionBuilder()
      .withId('q-multiple-other')
      .withType('multiple_choice')
      .withText('Quais sintomas você está sentindo?')
      .withOptions([
        { id: 'opt4', value: 'pain', text: 'Dor' },
        { id: 'opt5', value: 'insomnia', text: 'Insônia' },
        { id: 'opt6', value: 'anxiety', text: 'Ansiedade' },
      ])
      .allowOther(true)
      .build(),

  // Scale question
  scaleQuestion: () =>
    new QuizQuestionBuilder()
      .withId('q-scale')
      .withType('scale')
      .withText('Avalie seu bem-estar (0-10)')
      .withScale(0, 10)
      .build(),

  // Yes/No question
  yesNoQuestion: () =>
    new QuizQuestionBuilder()
      .withId('q-yesno')
      .withType('yes_no')
      .withText('Você está tomando seus medicamentos?')
      .build(),

  // Text question
  textQuestion: () =>
    new QuizQuestionBuilder()
      .withId('q-text')
      .withType('text')
      .withText('Alguma observação adicional?')
      .required(false)
      .build(),

  // Complete quiz session
  completeSession: () =>
    new QuizSessionBuilder()
      .withSessionId('session-complete')
      .withPatient('patient-123', 'João Silva')
      .withTemplate('template-123', 'Questionário Mensal')
      .withQuestions([
        fixtures.singleChoiceWithOther(),
        fixtures.yesNoQuestion(),
        fixtures.multipleChoiceWithOther(),
        fixtures.scaleQuestion(),
        fixtures.textQuestion(),
      ])
      .build(),

  // Expired session
  expiredSession: () => new QuizSessionBuilder().withSessionId('session-expired').expired().build(),
}
