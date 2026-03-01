/**
 * PatientTimeline Component Tests
 * Unit tests for patient timeline/history component
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { PatientTimeline } from '@/components/patients/PatientTimeline';
import { createMockPatient, resetPatientCounter } from '../../../test-utils/factories';

describe('PatientTimeline', () => {
  beforeEach(() => {
    resetPatientCounter();
  });

  it('should render timeline events in chronological order', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        {
          id: '1',
          type: 'diagnosis',
          date: '2024-01-15',
          description: 'Diagnóstico inicial',
        },
        {
          id: '2',
          type: 'treatment_start',
          date: '2024-01-20',
          description: 'Início do tratamento',
        },
        {
          id: '3',
          type: 'quiz_completed',
          date: '2024-01-25',
          description: 'Quiz mensal concluído',
        },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    const events = screen.getAllByRole('listitem');
    expect(events).toHaveLength(3);

    // Events should be in reverse chronological order (newest first)
    expect(within(events[0]).getByText(/Quiz mensal concluído/i)).toBeInTheDocument();
    expect(within(events[2]).getByText(/Diagnóstico inicial/i)).toBeInTheDocument();
  });

  it('should display different icons for different event types', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        { id: '1', type: 'diagnosis', date: '2024-01-15', description: 'Diagnóstico' },
        { id: '2', type: 'treatment_start', date: '2024-01-20', description: 'Tratamento' },
        { id: '3', type: 'quiz_completed', date: '2024-01-25', description: 'Quiz' },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByTestId('icon-diagnosis')).toBeInTheDocument();
    expect(screen.getByTestId('icon-treatment')).toBeInTheDocument();
    expect(screen.getByTestId('icon-quiz')).toBeInTheDocument();
  });

  it('should format dates correctly', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        {
          id: '1',
          type: 'diagnosis',
          date: '2024-01-15T10:30:00-03:00',
          description: 'Diagnóstico',
        },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByText(/15 de janeiro de 2024/i)).toBeInTheDocument();
  });

  it('should show "no events" message when timeline is empty', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByText(/nenhum evento registrado/i)).toBeInTheDocument();
  });

  it('should display event metadata when available', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        {
          id: '1',
          type: 'quiz_completed',
          date: '2024-01-25',
          description: 'Quiz mensal',
          metadata: {
            score: 85,
            completion_time: '15 minutos',
          },
        },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByText(/Score: 85/i)).toBeInTheDocument();
    expect(screen.getByText(/15 minutos/i)).toBeInTheDocument();
  });

  it('should group events by month', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        { id: '1', type: 'diagnosis', date: '2024-01-15', description: 'Evento 1' },
        { id: '2', type: 'treatment', date: '2024-01-20', description: 'Evento 2' },
        { id: '3', type: 'quiz', date: '2024-02-05', description: 'Evento 3' },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByText(/Janeiro 2024/i)).toBeInTheDocument();
    expect(screen.getByText(/Fevereiro 2024/i)).toBeInTheDocument();
  });

  it('should handle relative time display for recent events', () => {
    const today = new Date();
    const patient = {
      ...createMockPatient(),
      timeline: [
        {
          id: '1',
          type: 'quiz_completed',
          date: today.toISOString(),
          description: 'Quiz hoje',
        },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByText(/hoje/i)).toBeInTheDocument();
  });

  it('should be accessible with proper ARIA labels', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        { id: '1', type: 'diagnosis', date: '2024-01-15', description: 'Diagnóstico' },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByRole('list')).toHaveAttribute('aria-label', 'Linha do tempo do paciente');
    expect(screen.getByRole('listitem')).toHaveAttribute('aria-label');
  });

  it('should display doctor name for treatment events', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        {
          id: '1',
          type: 'treatment_start',
          date: '2024-01-20',
          description: 'Início do tratamento',
          doctor: 'Dr. João Silva',
        },
      ],
    };

    render(<PatientTimeline patient={patient} />);

    expect(screen.getByText(/Dr. João Silva/i)).toBeInTheDocument();
  });

  it('should filter events by type when filter is applied', () => {
    const patient = {
      ...createMockPatient(),
      timeline: [
        { id: '1', type: 'diagnosis', date: '2024-01-15', description: 'Diagnóstico' },
        { id: '2', type: 'quiz_completed', date: '2024-01-20', description: 'Quiz' },
      ],
    };

    render(<PatientTimeline patient={patient} filter="quiz_completed" />);

    const events = screen.getAllByRole('listitem');
    expect(events).toHaveLength(1);
    expect(screen.getByText(/Quiz/i)).toBeInTheDocument();
    expect(screen.queryByText(/Diagnóstico/i)).not.toBeInTheDocument();
  });
});
