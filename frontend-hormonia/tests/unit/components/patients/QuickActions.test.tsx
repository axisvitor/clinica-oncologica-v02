/**
 * QuickActions Component Tests
 * Unit tests for patient quick actions component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QuickActions } from '@/components/patients/QuickActions';
import { createMockPatient, resetPatientCounter } from '../../../test-utils/factories';

describe('QuickActions', () => {
  const mockOnSendQuiz = vi.fn();
  const mockOnViewDetails = vi.fn();
  const mockOnEdit = vi.fn();
  const mockOnDelete = vi.fn();

  beforeEach(() => {
    resetPatientCounter();
    vi.clearAllMocks();
  });

  it('should render all action buttons', () => {
    const patient = createMockPatient();

    render(
      <QuickActions
        patient={patient}
        onSendQuiz={mockOnSendQuiz}
        onViewDetails={mockOnViewDetails}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByRole('button', { name: /enviar questionário/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ver detalhes/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /editar/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /excluir/i })).toBeInTheDocument();
  });

  it('should call onSendQuiz when send quiz button is clicked', async () => {
    const patient = createMockPatient();
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onSendQuiz={mockOnSendQuiz} />);

    const sendQuizButton = screen.getByRole('button', { name: /enviar questionário/i });
    await user.click(sendQuizButton);

    expect(mockOnSendQuiz).toHaveBeenCalledWith(patient);
    expect(mockOnSendQuiz).toHaveBeenCalledTimes(1);
  });

  it('should call onViewDetails when view details button is clicked', async () => {
    const patient = createMockPatient();
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onViewDetails={mockOnViewDetails} />);

    const viewButton = screen.getByRole('button', { name: /ver detalhes/i });
    await user.click(viewButton);

    expect(mockOnViewDetails).toHaveBeenCalledWith(patient);
  });

  it('should call onEdit when edit button is clicked', async () => {
    const patient = createMockPatient();
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onEdit={mockOnEdit} />);

    const editButton = screen.getByRole('button', { name: /editar/i });
    await user.click(editButton);

    expect(mockOnEdit).toHaveBeenCalledWith(patient);
  });

  it('should show confirmation before delete', async () => {
    const patient = createMockPatient();
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onDelete={mockOnDelete} />);

    const deleteButton = screen.getByRole('button', { name: /excluir/i });
    await user.click(deleteButton);

    // Confirmation dialog should appear
    expect(screen.getByText(/tem certeza/i)).toBeInTheDocument();

    // Click confirm
    const confirmButton = screen.getByRole('button', { name: /confirmar/i });
    await user.click(confirmButton);

    expect(mockOnDelete).toHaveBeenCalledWith(patient);
  });

  it('should not delete if user cancels confirmation', async () => {
    const patient = createMockPatient();
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onDelete={mockOnDelete} />);

    const deleteButton = screen.getByRole('button', { name: /excluir/i });
    await user.click(deleteButton);

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: /cancelar/i });
    await user.click(cancelButton);

    expect(mockOnDelete).not.toHaveBeenCalled();
  });

  it('should disable send quiz button when patient has active quiz', () => {
    const patient = {
      ...createMockPatient(),
      has_active_quiz: true,
    };

    render(<QuickActions patient={patient} onSendQuiz={mockOnSendQuiz} />);

    const sendQuizButton = screen.getByRole('button', { name: /enviar questionário/i });
    expect(sendQuizButton).toBeDisabled();
  });

  it('should show tooltip on disabled send quiz button', async () => {
    const patient = {
      ...createMockPatient(),
      has_active_quiz: true,
    };
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onSendQuiz={mockOnSendQuiz} />);

    const sendQuizButton = screen.getByRole('button', { name: /enviar questionário/i });
    await user.hover(sendQuizButton);

    expect(await screen.findByText(/paciente já possui quiz ativo/i)).toBeInTheDocument();
  });

  it('should display loading state during action execution', async () => {
    const patient = createMockPatient();
    const slowAction = vi.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onSendQuiz={slowAction} />);

    const sendQuizButton = screen.getByRole('button', { name: /enviar questionário/i });
    await user.click(sendQuizButton);

    expect(screen.getByRole('button', { name: /enviando/i })).toBeDisabled();
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('should handle keyboard navigation', async () => {
    const patient = createMockPatient();
    const user = userEvent.setup();

    render(<QuickActions patient={patient} onSendQuiz={mockOnSendQuiz} />);

    // Tab to send quiz button
    await user.tab();
    expect(screen.getByRole('button', { name: /enviar questionário/i })).toHaveFocus();

    // Press Enter
    await user.keyboard('{Enter}');
    expect(mockOnSendQuiz).toHaveBeenCalled();
  });

  it('should render with proper accessibility attributes', () => {
    const patient = createMockPatient({ nome: 'João Silva' });

    render(<QuickActions patient={patient} onSendQuiz={mockOnSendQuiz} />);

    const sendQuizButton = screen.getByRole('button', { name: /enviar questionário/i });
    expect(sendQuizButton).toHaveAttribute('aria-label', 'Enviar questionário para João Silva');
  });

  it('should group actions in dropdown menu on mobile', () => {
    // Mock mobile viewport
    global.innerWidth = 375;
    global.dispatchEvent(new Event('resize'));

    const patient = createMockPatient();

    render(<QuickActions patient={patient} onSendQuiz={mockOnSendQuiz} isMobile={true} />);

    expect(screen.getByRole('button', { name: /ações/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /enviar questionário/i })).not.toBeInTheDocument();
  });
});
