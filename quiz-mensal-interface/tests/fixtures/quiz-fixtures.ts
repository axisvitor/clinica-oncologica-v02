/**
 * Test Fixtures Factory
 * Provides reusable test data builders
 */
import type { QuizSession, QuizQuestion, QuizOption } from '@/types/quiz'

/**
 * Quiz Option Builder
 */
export class QuizOptionBuilder {
  private option: QuizOption = {
    id: `opt-${Date.now()}`,
    value: 'default',
    text: 'Default Option'
  }

  withId(id: string): this {
    this.option.id = id
    return this
  }

  withValue(value: string): this {
    this.option.value = value
    return this
  }

  withText(text: string): this {
    this.option.text = text
    return this
  }

  withOther(allow: boolean = true): this {
    this.option.allow_other = allow
    return this
  }

  build(): QuizOption {
    return { ...this.option }
  }
}

/**
 * Quiz Question Builder
 */
export class QuizQuestionBuilder {
  private question: QuizQuestion = {
    id: `q-${Date.now()}`,
    order_index: 0,
    text: 'Default Question',
    type: 'text',
    required: true,
    allow_other: false
  }

  withId(id: string): this {
    this.question.id = id
    return this
  }

  withOrder(order: number): this {
    this.question.order_index = order
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
    quiz_session_id: `session-${Date.now()}`,
    patient_id: 'patient-123',
    patient_name: 'Test Patient',
    template_id: 'template-123',
    template_name: 'Test Template',
    status: 'in_progress',
    current_question_index: 0,
    total_questions: 1,
    expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    questions: [
      new QuizQuestionBuilder().withId('q1').withText('Test Question').build()
    ]
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

  withStatus(status: QuizSession['status']): this {
    this.session.status = status
    return this
  }

  withCurrentQuestion(index: number): this {
    this.session.current_question_index = index
    return this
  }

  withQuestions(questions: QuizQuestion[]): this {
    this.session.questions = questions
    this.session.total_questions = questions.length
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
  singleChoiceWithOther: () => new QuizQuestionBuilder()
    .withId('q-single-other')
    .withType('single_choice')
    .withText('Qual é o principal sintoma?')
    .withOptions([
      new QuizOptionBuilder().withId('opt1').withValue('headache').withText('Dor de cabeça').build(),
      new QuizOptionBuilder().withId('opt2').withValue('nausea').withText('Náusea').build(),
      new QuizOptionBuilder().withId('opt3').withValue('fatigue').withText('Fadiga').build()
    ])
    .allowOther(true)
    .build(),

  // Multiple choice question with "Outra" option
  multipleChoiceWithOther: () => new QuizQuestionBuilder()
    .withId('q-multiple-other')
    .withType('multiple_choice')
    .withText('Quais sintomas você está sentindo?')
    .withOptions([
      new QuizOptionBuilder().withId('opt4').withValue('pain').withText('Dor').build(),
      new QuizOptionBuilder().withId('opt5').withValue('insomnia').withText('Insônia').build(),
      new QuizOptionBuilder().withId('opt6').withValue('anxiety').withText('Ansiedade').build()
    ])
    .allowOther(true)
    .build(),

  // Scale question
  scaleQuestion: () => new QuizQuestionBuilder()
    .withId('q-scale')
    .withType('scale')
    .withText('Avalie seu bem-estar (0-10)')
    .withScale(0, 10)
    .build(),

  // Yes/No question
  yesNoQuestion: () => new QuizQuestionBuilder()
    .withId('q-yesno')
    .withType('yes_no')
    .withText('Você está tomando seus medicamentos?')
    .build(),

  // Text question
  textQuestion: () => new QuizQuestionBuilder()
    .withId('q-text')
    .withType('text')
    .withText('Alguma observação adicional?')
    .required(false)
    .build(),

  // Complete quiz session
  completeSession: () => new QuizSessionBuilder()
    .withSessionId('session-complete')
    .withPatient('patient-123', 'João Silva')
    .withTemplate('template-123', 'Questionário Mensal')
    .withQuestions([
      fixtures.scaleQuestion(),
      fixtures.yesNoQuestion(),
      fixtures.multipleChoiceWithOther(),
      fixtures.singleChoiceWithOther(),
      fixtures.textQuestion()
    ])
    .build(),

  // Expired session
  expiredSession: () => new QuizSessionBuilder()
    .withSessionId('session-expired')
    .expired()
    .build()
}
