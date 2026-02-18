/**
 * Quiz Test Data Factory
 * Provides reusable test data for quiz-related tests
 */

export interface QuizQuestion {
  id: string;
  type: 'multiple_choice' | 'single_choice' | 'yes_no' | 'scale' | 'text';
  question: string;
  options?: string[];
  required: boolean;
  order: number;
}

export interface QuizTemplate {
  id: string;
  title: string;
  description: string;
  questions: QuizQuestion[];
  created_at: string;
  updated_at: string;
}

export interface QuizSession {
  id: string;
  patient_id: string;
  quiz_template_id: string;
  status: 'not_started' | 'in_progress' | 'completed' | 'expired';
  started_at: string | null;
  completed_at: string | null;
  current_question_index: number;
  answers: Record<string, any>;
  score: number | null;
}

let questionIdCounter = 1;
let templateIdCounter = 1;
let sessionIdCounter = 1;

export const createMockQuestion = (
  type: QuizQuestion['type'] = 'multiple_choice',
  overrides?: Partial<QuizQuestion>
): QuizQuestion => {
  const baseQuestion: QuizQuestion = {
    id: `question-${questionIdCounter++}`,
    type,
    question: 'Pergunta exemplo',
    required: true,
    order: 1,
    ...overrides,
  };

  if (type === 'multiple_choice' || type === 'single_choice') {
    baseQuestion.options = overrides?.options || [
      'Opção 1',
      'Opção 2',
      'Opção 3',
      'Opção 4',
    ];
  }

  return baseQuestion;
};

export const createMockQuizTemplate = (overrides?: Partial<QuizTemplate>): QuizTemplate => ({
  id: `template-${templateIdCounter++}`,
  title: 'Questionário de Avaliação Mensal',
  description: 'Avaliação do estado de saúde do paciente',
  questions: [
    createMockQuestion('multiple_choice', { order: 1, question: 'Como você se sente hoje?' }),
    createMockQuestion('scale', { order: 2, question: 'Nível de dor (0-10)' }),
    createMockQuestion('yes_no', { order: 3, question: 'Teve náuseas esta semana?' }),
    createMockQuestion('text', { order: 4, question: 'Observações adicionais' }),
  ],
  created_at: '2024-01-01T00:00:00-03:00',
  updated_at: '2024-01-01T00:00:00-03:00',
  ...overrides,
});

export const createMockQuizSession = (overrides?: Partial<QuizSession>): QuizSession => ({
  id: `session-${sessionIdCounter++}`,
  patient_id: 'patient-1',
  quiz_template_id: 'template-1',
  status: 'not_started',
  started_at: null,
  completed_at: null,
  current_question_index: 0,
  answers: {},
  score: null,
  ...overrides,
});

export const createInProgressQuizSession = (currentIndex = 2): QuizSession =>
  createMockQuizSession({
    status: 'in_progress',
    started_at: new Date().toISOString(),
    current_question_index: currentIndex,
    answers: {
      'question-1': ['Opção 1', 'Opção 2'],
      'question-2': 7,
    },
  });

export const createCompletedQuizSession = (): QuizSession =>
  createMockQuizSession({
    status: 'completed',
    started_at: new Date(Date.now() - 3600000).toISOString(),
    completed_at: new Date().toISOString(),
    current_question_index: 4,
    answers: {
      'question-1': ['Opção 1'],
      'question-2': 5,
      'question-3': 'sim',
      'question-4': 'Tudo bem',
    },
    score: 85,
  });

export const createAllQuestionTypes = (): QuizQuestion[] => [
  createMockQuestion('multiple_choice', {
    question: 'Quais sintomas você está sentindo?',
    options: ['Náusea', 'Fadiga', 'Dor', 'Insônia'],
  }),
  createMockQuestion('single_choice', {
    question: 'Como está seu apetite?',
    options: ['Excelente', 'Bom', 'Regular', 'Ruim'],
  }),
  createMockQuestion('yes_no', {
    question: 'Você tomou todos os medicamentos prescritos?',
  }),
  createMockQuestion('scale', {
    question: 'Nível de dor (0-10)',
  }),
  createMockQuestion('text', {
    question: 'Descreva qualquer outro sintoma',
  }),
];

export const resetQuizCounters = () => {
  questionIdCounter = 1;
  templateIdCounter = 1;
  sessionIdCounter = 1;
};
