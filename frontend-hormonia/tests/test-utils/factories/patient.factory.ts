/**
 * Patient Test Data Factory
 * Provides reusable test data for patient-related tests
 */

import { Patient } from '@/types/api';

let patientIdCounter = 1;

export const createMockPatient = (overrides?: Partial<Patient>): Patient => ({
  id: `patient-${patientIdCounter++}`,
  nome: 'João da Silva',
  email: 'joao.silva@example.com',
  telefone: '(11) 98765-4321',
  data_nascimento: '1980-05-15',
  cpf: '123.456.789-00',
  tipo_cancer: 'mama',
  estadio: 'II',
  tratamento_atual: 'quimioterapia',
  medico_responsavel: 'Dr. Maria Santos',
  data_diagnostico: '2024-01-15',
  created_at: '2024-01-15T10:00:00Z',
  updated_at: '2024-01-15T10:00:00Z',
  active: true,
  ...overrides,
});

export const createMockPatients = (count: number, overrides?: Partial<Patient>): Patient[] => {
  return Array.from({ length: count }, (_, index) =>
    createMockPatient({
      ...overrides,
      id: `patient-${index + 1}`,
      nome: `Paciente ${index + 1}`,
      email: `paciente${index + 1}@example.com`,
    })
  );
};

export const createPatientWithQuizzes = (overrides?: Partial<Patient>) => {
  const patient = createMockPatient(overrides);
  return {
    ...patient,
    quiz_sessions: [
      {
        id: 'session-1',
        patient_id: patient.id,
        quiz_template_id: 'template-1',
        status: 'completed',
        started_at: '2024-01-20T10:00:00Z',
        completed_at: '2024-01-20T10:30:00Z',
        score: 85,
      },
      {
        id: 'session-2',
        patient_id: patient.id,
        quiz_template_id: 'template-2',
        status: 'in_progress',
        started_at: '2024-01-25T14:00:00Z',
        completed_at: null,
        score: null,
      },
    ],
  };
};

export const resetPatientCounter = () => {
  patientIdCounter = 1;
};
