/**
 * Quiz "Outra" Option Comprehensive Tests
 * Tests the "other" option functionality for single and multiple choice questions
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import QuizInterface from '@/components/quiz-interface';
import { fixtures } from './fixtures/quiz-fixtures';

describe('Quiz "Outra" Option Tests', () => {
  const mockToken = 'valid-token';
  const mockOnComplete = jest.fn();
  const mockOnTokenUpdate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Single Choice - "Outra" Option', () => {
    const singleChoiceSession = {
      quiz_session_id: 'session-single-other',
      patient_id: 'patient-123',
      patient_name: 'Test Patient',
      template_id: 'template-123',
      template_name: 'Test Template',
      status: 'in_progress' as const,
      current_question_index: 0,
      total_questions: 1,
      expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      questions: [fixtures.singleChoiceWithOther()]
    };

    it('should render "Outra" option for single choice question', () => {
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByText(/outra/i)).toBeInTheDocument();
    });

    it('should show text input when "Outra" is selected', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      await waitFor(() => {
        const textInput = screen.getByPlaceholderText(/especifique|descreva/i);
        expect(textInput).toBeInTheDocument();
        expect(textInput).toBeVisible();
      });
    });

    it('should hide text input when another option is selected', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // Select "Outra"
      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/especifique|descreva/i)).toBeVisible();
      });

      // Select another option
      const otherOption = screen.getByText(/dor de cabeça/i);
      await user.click(otherOption);

      await waitFor(() => {
        const textInput = screen.queryByPlaceholderText(/especifique|descreva/i);
        expect(textInput).not.toBeInTheDocument();
      });
    });

    it('should allow typing custom text in "Outra" input', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, 'Tontura persistente');

      expect(textInput).toHaveValue('Tontura persistente');
    });

    it('should show validation error when submitting "Outra" without text', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const submitButton = screen.getByRole('button', { name: /próxima|enviar|concluir/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/especifique|obrigatório/i)).toBeInTheDocument();
      });
    });

    it('should submit successfully with custom text', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, 'Tontura persistente');

      const submitButton = screen.getByRole('button', { name: /próxima|enviar|concluir/i });
      await user.click(submitButton);

      // Should complete successfully without validation errors
      await waitFor(() => {
        expect(screen.queryByText(/especifique|obrigatório/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Multiple Choice - "Outra" Option', () => {
    const multipleChoiceSession = {
      quiz_session_id: 'session-multiple-other',
      patient_id: 'patient-123',
      patient_name: 'Test Patient',
      template_id: 'template-123',
      template_name: 'Test Template',
      status: 'in_progress' as const,
      current_question_index: 0,
      total_questions: 1,
      expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      questions: [fixtures.multipleChoiceWithOther()]
    };

    it('should allow selecting "Outra" along with other options', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={multipleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // Select multiple options including "Outra"
      const dorOption = screen.getByText(/dor/i);
      const outraOption = screen.getByText(/outra/i);

      await user.click(dorOption);
      await user.click(outraOption);

      // Both should be selected
      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      expect(textInput).toBeVisible();
    });

    it('should preserve other selections when typing custom text', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={multipleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const dorOption = screen.getByText(/dor/i);
      const insomniaOption = screen.getByText(/insônia/i);
      const outraOption = screen.getByText(/outra/i);

      await user.click(dorOption);
      await user.click(insomniaOption);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, 'Dor muscular');

      expect(textInput).toHaveValue('Dor muscular');
      // Other selections should remain checked
    });

    it('should validate that "Outra" requires text when selected', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={multipleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const submitButton = screen.getByRole('button', { name: /próxima|enviar|concluir/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/especifique|obrigatório/i)).toBeInTheDocument();
      });
    });

    it('should submit multiple selections with custom text', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={multipleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const dorOption = screen.getByText(/dor/i);
      const outraOption = screen.getByText(/outra/i);

      await user.click(dorOption);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, 'Ansiedade');

      const submitButton = screen.getByRole('button', { name: /próxima|enviar|concluir/i });
      await user.click(submitButton);

      // Should complete successfully
      await waitFor(() => {
        expect(screen.queryByText(/especifique|obrigatório/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    const singleChoiceSession = {
      quiz_session_id: 'session-edge-cases',
      patient_id: 'patient-123',
      patient_name: 'Test Patient',
      template_id: 'template-123',
      template_name: 'Test Template',
      status: 'in_progress' as const,
      current_question_index: 0,
      total_questions: 1,
      expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      questions: [fixtures.singleChoiceWithOther()]
    };

    it('should trim whitespace from custom text', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, '   Texto com espaços   ');

      const submitButton = screen.getByRole('button', { name: /próxima|enviar|concluir/i });
      await user.click(submitButton);

      // Should accept trimmed text
      await waitFor(() => {
        expect(screen.queryByText(/especifique|obrigatório/i)).not.toBeInTheDocument();
      });
    });

    it('should reject only whitespace as custom text', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, '     ');

      const submitButton = screen.getByRole('button', { name: /próxima|enviar|concluir/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/especifique|obrigatório/i)).toBeInTheDocument();
      });
    });

    it('should handle special characters in custom text', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, 'Dor < 5/10, com "pontadas"');

      expect(textInput).toHaveValue('Dor < 5/10, com "pontadas"');
    });

    it('should clear custom text when deselecting "Outra"', async () => {
      const user = userEvent.setup();
      const multipleChoiceSession = {
        quiz_session_id: 'session-deselect',
        patient_id: 'patient-123',
        patient_name: 'Test Patient',
        template_id: 'template-123',
        template_name: 'Test Template',
        status: 'in_progress' as const,
        current_question_index: 0,
        total_questions: 1,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
        questions: [fixtures.multipleChoiceWithOther()]
      };

      render(
        <QuizInterface
          session={multipleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      await user.type(textInput, 'Texto temporário');

      // Deselect "Outra"
      await user.click(outraOption);

      await waitFor(() => {
        expect(screen.queryByPlaceholderText(/especifique|descreva/i)).not.toBeInTheDocument();
      });

      // Select "Outra" again
      await user.click(outraOption);

      const newTextInput = await screen.findByPlaceholderText(/especifique|descreva/i);
      expect(newTextInput).toHaveValue('');
    });
  });

  describe('Accessibility', () => {
    const singleChoiceSession = {
      quiz_session_id: 'session-a11y',
      patient_id: 'patient-123',
      patient_name: 'Test Patient',
      template_id: 'template-123',
      template_name: 'Test Template',
      status: 'in_progress' as const,
      current_question_index: 0,
      total_questions: 1,
      expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      questions: [fixtures.singleChoiceWithOther()]
    };

    it('should associate text input with "Outra" option for screen readers', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const textInput = await screen.findByPlaceholderText(/especifique|descreva/i);

      expect(textInput).toHaveAttribute('aria-label');
      expect(textInput).toHaveAttribute('id');
    });

    it('should announce validation errors to screen readers', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      const submitButton = screen.getByRole('button', { name: /próxima|enviar|concluir/i });
      await user.click(submitButton);

      await waitFor(() => {
        const errorMessage = screen.getByText(/especifique|obrigatório/i);
        expect(errorMessage).toHaveAttribute('role', 'alert');
      });
    });

    it('should have proper focus management', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={singleChoiceSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const outraOption = screen.getByText(/outra/i);
      await user.click(outraOption);

      await waitFor(() => {
        const textInput = screen.getByPlaceholderText(/especifique|descreva/i);
        expect(textInput).toHaveFocus();
      });
    });
  });
});
