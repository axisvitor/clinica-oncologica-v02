/**
 * Public Quiz Access Component
 *
 * Public-facing component for patients to access and complete quizzes via link.
 * This component does not require authentication.
 */
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMonthlyQuiz } from '../hooks/useMonthlyQuiz';
import { MonthlyQuizAccess } from '../types';

export const PublicQuizAccess: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { accessQuiz, submitQuizResponse, loading, error } = useMonthlyQuiz();
  const [quizData, setQuizData] = useState<MonthlyQuizAccess | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isCompleted, setIsCompleted] = useState(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const token = searchParams.get('token');

  useEffect(() => {
    if (token) {
      loadQuiz();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadQuiz is stable and should only run when token changes
  }, [token]);

  const loadQuiz = async () => {
    if (!token) return;

    setSubmissionError(null);
    const data = await accessQuiz(token);
    if (data) {
      setQuizData(data);
      setCurrentQuestionIndex(data.current_question_index);
    }
  };

  const handleAnswer = (questionId: string, value: string) => {
    setAnswers({ ...answers, [questionId]: value });
  };

  const handleSubmit = async () => {
    if (!token || !quizData) return;

    const currentQuestion = quizData.questions[currentQuestionIndex];
    if (!currentQuestion) return;

    const response = await submitQuizResponse({
      token,
      quiz_id: quizData.quiz_id,
      question_id: currentQuestion.id,
      response_value: answers[currentQuestion.id] || ''
    });

    if (!response || !response.success) {
      setSubmissionError(response?.message || 'Não foi possível registrar sua resposta. Tente novamente.');
      return;
    }

    setSubmissionError(null);

    if (currentQuestionIndex < quizData.total_questions - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    } else {
      setIsCompleted(true);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md">
          <p className="text-red-600">Token de acesso inválido</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p>Carregando quiz...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md max-w-md">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={loadQuiz}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Tentar Novamente
          </button>
        </div>
      </div>
    );
  }

  if (isCompleted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-lg shadow-md max-w-md text-center">
          <div className="text-green-600 text-5xl mb-4">✓</div>
          <h2 className="text-2xl font-bold mb-4">Quiz Concluído!</h2>
          <p className="text-gray-600">
            Obrigado por completar o questionário mensal. Suas respostas foram registradas com sucesso.
          </p>
        </div>
      </div>
    );
  }

  if (!quizData) {
    return null;
  }

  const currentQuestion = quizData.questions[currentQuestionIndex];
  if (!currentQuestion) {
    return null;
  }
  const progress = ((currentQuestionIndex + 1) / quizData.total_questions) * 100;

  return (
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="bg-white p-6 rounded-lg shadow-md mb-6">
          <h1 className="text-2xl font-bold mb-2">{quizData.template_name}</h1>
          <p className="text-gray-600">Olá, {quizData.patient_name}</p>

          {/* Progress Bar */}
          <div className="mt-4">
            <div className="flex justify-between text-sm text-gray-600 mb-2">
              <span>Pergunta {currentQuestionIndex + 1} de {quizData.total_questions}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
        </div>

        {/* Question */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <h2 className="text-lg font-semibold mb-4">{currentQuestion.text}</h2>

          {currentQuestion.description && (
            <p className="text-gray-600 mb-4">{currentQuestion.description}</p>
          )}

          {/* Answer Input based on question type */}
          {currentQuestion.type === 'multiple_choice' && (
            <div className="space-y-2">
              {currentQuestion.options?.map((option: { id: string; text: string }) => (
                <label key={option.id} className="flex items-center p-3 border rounded hover:bg-gray-50 cursor-pointer">
                  <input
                    type="radio"
                    name={currentQuestion.id}
                    value={option.id}
                    checked={answers[currentQuestion.id] === option.id}
                    onChange={(e) => handleAnswer(currentQuestion.id, e.target.value)}
                    className="mr-3"
                  />
                  <span>{option.text}</span>
                </label>
              ))}
            </div>
          )}

          {currentQuestion.type === 'open_text' && (
            <textarea
              value={answers[currentQuestion.id] || ''}
              onChange={(e) => handleAnswer(currentQuestion.id, e.target.value)}
              className="w-full p-3 border rounded"
              rows={4}
              placeholder="Digite sua resposta aqui..."
            />
          )}

          {currentQuestion.type === 'scale' && (
            <div>
              <input
                type="range"
                min={currentQuestion.validation_rules?.[0]?.min || 0}
                max={currentQuestion.validation_rules?.[0]?.max || 10}
                value={answers[currentQuestion.id] || 5}
                onChange={(e) => handleAnswer(currentQuestion.id, e.target.value)}
                className="w-full"
              />
              <div className="text-center text-2xl font-bold mt-2">
                {answers[currentQuestion.id] || 5}
              </div>
            </div>
          )}

          {submissionError && (
            <p className="mt-4 text-sm text-red-600">{submissionError}</p>
          )}

          {/* Submit Button */}
          <button
            onClick={handleSubmit}
            disabled={!answers[currentQuestion.id] || loading}
            className="w-full mt-6 py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {currentQuestionIndex < quizData.total_questions - 1 ? 'Próxima' : 'Finalizar'}
          </button>
        </div>
      </div>
    </div>
  );
};

