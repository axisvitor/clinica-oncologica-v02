/**
 * PatientStats Component Tests
 * Unit tests for patient statistics display component
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PatientStats } from '@/components/patients/PatientStats';
import { createMockPatient, resetPatientCounter } from '../../../test-utils/factories';

describe('PatientStats', () => {
  beforeEach(() => {
    resetPatientCounter();
  });

  it('should render patient statistics correctly', () => {
    const patient = createMockPatient({
      nome: 'João Silva',
      tipo_cancer: 'mama',
      estadio: 'II',
      tratamento_atual: 'quimioterapia',
    });

    render(<PatientStats patient={patient} />);

    expect(screen.getByText('João Silva')).toBeInTheDocument();
    expect(screen.getByText(/mama/i)).toBeInTheDocument();
    expect(screen.getByText(/Estádio II/i)).toBeInTheDocument();
    expect(screen.getByText(/quimioterapia/i)).toBeInTheDocument();
  });

  it('should display treatment start date if available', () => {
    const patient = createMockPatient({
      data_diagnostico: '2024-01-15',
    });

    render(<PatientStats patient={patient} />);

    expect(screen.getByText(/15\/01\/2024/)).toBeInTheDocument();
  });

  it('should handle missing optional fields gracefully', () => {
    const patient = createMockPatient({
      medico_responsavel: undefined,
      data_diagnostico: undefined,
    });

    render(<PatientStats patient={patient} />);

    expect(screen.getByText(/não informado/i)).toBeInTheDocument();
  });

  it('should format cancer type with proper capitalization', () => {
    const patient = createMockPatient({
      tipo_cancer: 'pulmao',
    });

    render(<PatientStats patient={patient} />);

    expect(screen.getByText(/Pulmão/i)).toBeInTheDocument();
  });

  it('should display active treatment indicator', () => {
    const patient = createMockPatient({
      active: true,
      tratamento_atual: 'radioterapia',
    });

    render(<PatientStats patient={patient} />);

    const activeIndicator = screen.getByTestId('active-treatment-indicator');
    expect(activeIndicator).toHaveClass('bg-green-500');
  });

  it('should display inactive treatment indicator', () => {
    const patient = createMockPatient({
      active: false,
    });

    render(<PatientStats patient={patient} />);

    const inactiveIndicator = screen.getByTestId('active-treatment-indicator');
    expect(inactiveIndicator).toHaveClass('bg-gray-400');
  });

  it('should display quiz completion stats when available', () => {
    const patient = {
      ...createMockPatient(),
      quiz_sessions: [
        { status: 'completed' },
        { status: 'completed' },
        { status: 'in_progress' },
      ],
    };

    render(<PatientStats patient={patient} />);

    expect(screen.getByText(/2 concluídos/i)).toBeInTheDocument();
    expect(screen.getByText(/1 em andamento/i)).toBeInTheDocument();
  });

  it('should calculate days since diagnosis', () => {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const patient = createMockPatient({
      data_diagnostico: thirtyDaysAgo.toISOString().split('T')[0],
    });

    render(<PatientStats patient={patient} />);

    expect(screen.getByText(/30 dias/i)).toBeInTheDocument();
  });

  it('should render accessibility labels correctly', () => {
    const patient = createMockPatient();

    render(<PatientStats patient={patient} />);

    expect(screen.getByLabelText(/estatísticas do paciente/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/tipo de câncer/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/tratamento atual/i)).toBeInTheDocument();
  });
});
