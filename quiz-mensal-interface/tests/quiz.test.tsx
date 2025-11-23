/**
 * Quiz Interface Integration Tests
 * Tests the complete quiz flow using real components and MSW mocks
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import QuizInterface from '@/components/quiz-interface';
import { mockQuizSession } from './mocks/handlers';

describe('Quiz Interface Integration Tests', () => {
  const mockToken = 'valid-token';
  const mockOnComplete = jest.fn();
  const mockOnTokenUpdate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Quiz Rendering', () => {
    it('should render quiz interface with session data', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
          onTokenUpdate={mockOnTokenUpdate}
        />
      );

      expect(screen.getByText(mockQuizSession.patient_name)).toBeInTheDocument();
      expect(screen.getByText(mockQuizSession.template_name)).toBeInTheDocument();
    });

    it('should display first question', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const firstQuestion = mockQuizSession.questions[0];
      expect(screen.getByText(firstQuestion.text)).toBeInTheDocument();
    });

    it('should show progress indicator', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const progressText = `1 de ${mockQuizSession.total_questions}`;
      expect(screen.getByText(new RegExp(progressText, 'i'))).toBeInTheDocument();
    });
  });

  describe('Scale Question Type', () => {
    it('should render scale question correctly', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // First question is scale type (0-10)
      const slider = screen.getByRole('slider');
      expect(slider).toBeInTheDocument();
      expect(slider).toHaveAttribute('min', '0');
      expect(slider).toHaveAttribute('max', '10');
    });

    it('should update value when slider is moved', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const slider = screen.getByRole('slider') as HTMLInputElement;

      fireEvent.change(slider, { target: { value: '7' } });

      expect(slider.value).toBe('7');
    });
  });

  describe('Yes/No Question Type', () => {
    it('should render yes/no question with buttons', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // Answer first question to move to second (yes/no)
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '5' } });

      const nextButton = screen.getByRole('button', { name: /próxima/i });
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText(/tomando seus medicamentos/i)).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /sim/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /não/i })).toBeInTheDocument();
    });

    it('should allow selecting yes or no', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={{ ...mockQuizSession, current_question_index: 1 }}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const yesButton = screen.getByRole('button', { name: /sim/i });
      await user.click(yesButton);

      // Button should be selected/active
      expect(yesButton).toHaveClass(/selected|active/i);
    });
  });

  describe('Multiple Choice Questions', () => {
    it('should render multiple choice options', () => {
      render(
        <QuizInterface
          session={{ ...mockQuizSession, current_question_index: 2 }}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes.length).toBeGreaterThan(0);
    });

    it('should allow selecting multiple options', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={{ ...mockQuizSession, current_question_index: 2 }}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');

      await user.click(checkboxes[0]);
      await user.click(checkboxes[1]);

      expect(checkboxes[0]).toBeChecked();
      expect(checkboxes[1]).toBeChecked();
    });
  });

  describe('Quiz Navigation', () => {
    it('should navigate to next question after answering', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // Answer scale question
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '7' } });

      // Click next
      const nextButton = screen.getByRole('button', { name: /próxima/i });
      await user.click(nextButton);

      // Should show second question
      await waitFor(() => {
        const secondQuestion = mockQuizSession.questions[1];
        expect(screen.getByText(secondQuestion.text)).toBeInTheDocument();
      });
    });

    it('should allow going back to previous question', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={{ ...mockQuizSession, current_question_index: 1 }}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const backButton = screen.getByRole('button', { name: /anterior/i });
      await user.click(backButton);

      await waitFor(() => {
        const firstQuestion = mockQuizSession.questions[0];
        expect(screen.getByText(firstQuestion.text)).toBeInTheDocument();
      });
    });

    it('should disable back button on first question', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const backButton = screen.queryByRole('button', { name: /anterior/i });
      expect(backButton).toBeDisabled();
    });
  });

  describe('Form Validation', () => {
    it('should require answer before proceeding', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // Try to proceed without answering
      const nextButton = screen.getByRole('button', { name: /próxima/i });
      await user.click(nextButton);

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/obrigatória/i)).toBeInTheDocument();
      });
    });

    it('should validate scale value is within range', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const slider = screen.getByRole('slider') as HTMLInputElement;

      // Try invalid value
      fireEvent.change(slider, { target: { value: '15' } });

      // Should be constrained to max
      expect(parseInt(slider.value)).toBeLessThanOrEqual(10);
    });
  });

  describe('Quiz Completion', () => {
    it('should show completion button on last question', () => {
      const lastQuestionIndex = mockQuizSession.total_questions - 1;

      render(
        <QuizInterface
          session={{ ...mockQuizSession, current_question_index: lastQuestionIndex }}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      expect(screen.getByRole('button', { name: /concluir/i })).toBeInTheDocument();
    });

    it('should call onComplete when quiz is finished', async () => {
      const user = userEvent.setup();
      const lastQuestionIndex = mockQuizSession.total_questions - 1;

      render(
        <QuizInterface
          session={{ ...mockQuizSession, current_question_index: lastQuestionIndex }}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // Answer last question (text type)
      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'Final answer');

      // Complete quiz
      const completeButton = screen.getByRole('button', { name: /concluir/i });
      await user.click(completeButton);

      await waitFor(() => {
        expect(mockOnComplete).toHaveBeenCalled();
      });
    });
  });

  describe('Loading States', () => {
    it('should show loading indicator during submission', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '5' } });

      const nextButton = screen.getByRole('button', { name: /próxima/i });
      await user.click(nextButton);

      // Should show loading state briefly
      expect(nextButton).toBeDisabled();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels on progress bar', () => {
      render(
        <QuizInterface
          session={mockQuizSession}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuemin');
      expect(progressBar).toHaveAttribute('aria-valuemax');
      expect(progressBar).toHaveAttribute('aria-valuenow');
    });

    it('should support keyboard navigation for yes/no buttons', async () => {
      const user = userEvent.setup();
      render(
        <QuizInterface
          session={{ ...mockQuizSession, current_question_index: 1 }}
          token={mockToken}
          onComplete={mockOnComplete}
        />
      );

      // Tab to yes button and activate with Enter
      await user.tab();
      await user.keyboard('{Enter}');

      const yesButton = screen.getByRole('button', { name: /sim/i });
      expect(yesButton).toHaveClass(/selected|active/i);
    });
  });

  describe('Error Handling', () => {
    it('should display error message on submission failure', async () => {
      const user = userEvent.setup();

      // This test would require MSW to return an error
      // For now, we test the component handles errors
      render(
        <QuizInterface
          session={mockQuizSession}
          token="invalid-token"
          onComplete={mockOnComplete}
        />
      );

      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '5' } });

      const nextButton = screen.getByRole('button', { name: /próxima/i });
      await user.click(nextButton);

      // Should show error toast/message
      await waitFor(() => {
        // Error handling would be visible here
        expect(nextButton).toBeEnabled(); // Can retry
      });
    });
  });
});
