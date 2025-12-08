/**
 * Mock data for tests
 * Provides realistic test data for various entities
 */

export const mockQuizTemplate = {
  id: 'quiz-template-1',
  name: 'Questionário Mensal de Sintomas',
  version: '1.0',
  questions: [
    {
      id: 'q1',
      type: 'multiple_choice' as const,
      text: 'Como você avalia sua dor hoje?',
      description: 'Escala de 1 a 5',
      required: true,
      options: [
        { id: 'opt1', text: 'Sem dor', value: 1, is_correct: false },
        { id: 'opt2', text: 'Dor leve', value: 2, is_correct: false },
        { id: 'opt3', text: 'Dor moderada', value: 3, is_correct: false },
        { id: 'opt4', text: 'Dor forte', value: 4, is_correct: false },
        { id: 'opt5', text: 'Dor insuportável', value: 5, is_correct: false }
      ]
    },
    {
      id: 'q2',
      type: 'yes_no' as const,
      text: 'Você teve náuseas esta semana?',
      required: true
    },
    {
      id: 'q3',
      type: 'open_text' as const,
      text: 'Descreva quaisquer outros sintomas',
      required: false
    }
  ],
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z'
}

export const mockQuizTemplates = [
  mockQuizTemplate,
  {
    ...mockQuizTemplate,
    id: 'quiz-template-2',
    name: 'Avaliação de Qualidade de Vida',
    version: '2.0'
  }
]

export const mockQuizAnalytics = {
  quiz_template_id: 'quiz-template-1',
  total_responses: 150,
  completion_rate: 0.85,
  average_completion_time: 180,
  question_analytics: [
    {
      question_id: 'q1',
      response_distribution: {
        '1': 20,
        '2': 40,
        '3': 50,
        '4': 30,
        '5': 10
      }
    }
  ],
  trends: {
    weekly: [85, 88, 90, 85],
    monthly: [82, 84, 85]
  }
}

export const mockPatient = {
  id: 'patient-1',
  full_name: 'Maria Silva',
  date_of_birth: '1970-01-15',
  cpf: '123.456.789-00',
  email: 'maria.silva@email.com',
  phone: '(11) 98765-4321',
  address: 'Rua das Flores, 123',
  medical_record_number: 'MRN12345',
  diagnosis: 'Câncer de mama',
  treatment_stage: 'Em tratamento',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z'
}

export const mockPatients = [
  mockPatient,
  {
    ...mockPatient,
    id: 'patient-2',
    full_name: 'João Santos',
    cpf: '987.654.321-00',
    email: 'joao.santos@email.com',
    diagnosis: 'Câncer de pulmão'
  }
]

export const mockUserProfile = {
  id: 'user-1',
  email: 'doctor@clinic.com',
  full_name: 'Dr. João Médico',
  phone: '(11) 91234-5678',
  specialty: 'Oncologia',
  role: 'doctor',
  is_active: true,
  permissions: ['read:patients', 'write:patients', 'read:quiz', 'write:quiz'],
  created_at: '2023-01-01T00:00:00Z'
}

export const mockUserPreferences = {
  theme: 'light' as const,
  language: 'pt-BR',
  notifications_enabled: true,
  email_notifications: true,
  push_notifications: false,
  accent_color: '#0066cc'
}

export const mockNotificationPreferences = {
  patient_updates: true,
  quiz_responses: true,
  system_alerts: true,
  weekly_reports: false
}

export const mockDashboardStats = {
  total_patients: 150,
  active_patients: 120,
  pending_quizzes: 25,
  completed_quizzes_today: 8,
  completion_rate: 0.85,
  average_response_time: 180
}

export const mockQuizResponse = {
  id: 'response-1',
  quiz_template_id: 'quiz-template-1',
  patient_id: 'patient-1',
  answers: {
    q1: '3',
    q2: 'yes',
    q3: 'Sentindo cansaço excessivo'
  },
  completed_at: '2025-01-15T10:30:00Z',
  completion_time_seconds: 180
}

export const mockApiError = {
  message: 'Erro ao processar requisição',
  code: 'API_ERROR',
  details: {}
}

export const mockValidationError = {
  message: 'Dados inválidos',
  code: 'VALIDATION_ERROR',
  details: {
    email: 'Email inválido',
    phone: 'Telefone deve ter 11 dígitos'
  }
}