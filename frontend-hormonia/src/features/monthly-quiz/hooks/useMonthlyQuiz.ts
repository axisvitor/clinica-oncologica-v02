/**
 * Monthly Quiz Hook for Frontend
 *
 * React hook for managing monthly quiz via link functionality.
 */
import { useState, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';
import type { QuizLinkStatus as ApiQuizLinkStatus } from '@/lib/api-client/monthly-quiz';

// Define types inline since ../types doesn't exist
interface MonthlyQuizLinkCreate {
  patient_id: string
  quiz_template_id: string
  expires_in_days?: number
}

interface MonthlyQuizLink {
  session_id?: string
  quiz_session_id?: string
  patient_id: string
  quiz_template_id: string
  link_url?: string
  link?: string
  expires_at: string
  created_at: string
}

interface MonthlyQuizAccessRequest {
  token: string
}

// Import types from centralized location
import type { MonthlyQuizAccess, MonthlyQuizSubmit } from '../types'

interface MonthlyQuizStats {
  total_sent: number
  total_accessed?: number
  total_active?: number
  total_completed: number
  total_expired?: number
  completion_rate: number
  average_score?: number
  expiration_rate?: number
}

// Import bulk types from centralized location
import type { BulkQuizLinkCreate, BulkQuizLinkResponse } from '../types'

export interface UseMonthlyQuizReturn {
  loading: boolean
  error: string | null
  createQuizLink: (linkData: MonthlyQuizLinkCreate) => Promise<MonthlyQuizLink | null>
  createBulkQuizLinks: (bulkData: BulkQuizLinkCreate) => Promise<BulkQuizLinkResponse | null>
  getQuizLinkStatus: (sessionId: string) => Promise<ApiQuizLinkStatus | null>
  getQuizStats: (startDate?: string, endDate?: string) => Promise<MonthlyQuizStats | null>
  accessQuiz: (token: string) => Promise<MonthlyQuizAccess | null>
  submitQuizResponse: (submitData: MonthlyQuizSubmit) => Promise<{ success: boolean; message: string } | null>
}

export function useMonthlyQuiz(): UseMonthlyQuizReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Create a monthly quiz link for a patient
   */
  const createQuizLink = useCallback(async (
    linkData: MonthlyQuizLinkCreate
  ): Promise<MonthlyQuizLink | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.monthlyQuiz.createLink(linkData);
      return response;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create quiz link';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Create quiz links for multiple patients
   */
  const createBulkQuizLinks = useCallback(async (
    bulkData: BulkQuizLinkCreate
  ): Promise<BulkQuizLinkResponse | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.monthlyQuiz.bulkCreate(bulkData);
      return response;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create bulk quiz links';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Get quiz link status
   */
  const getQuizLinkStatus = useCallback(async (
    sessionId: string
  ): Promise<ApiQuizLinkStatus | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.monthlyQuiz.getStatus(sessionId);
      return response;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get quiz link status';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Get monthly quiz statistics
   */
  const getQuizStats = useCallback(async (
    startDate?: string,
    endDate?: string
  ): Promise<MonthlyQuizStats | null> => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);

      const statsParams: { start_date?: string; end_date?: string } = {}
      if (startDate) statsParams.start_date = startDate
      if (endDate) statsParams.end_date = endDate

      const response = await apiClient.monthlyQuiz.getStats(statsParams);
      return response;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to get quiz statistics';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Access quiz via token (public endpoint)
   */
  const accessQuiz = useCallback(async (
    token: string
  ): Promise<MonthlyQuizAccess | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.request<MonthlyQuizAccess>(
        '/api/v2/monthly-quiz-public/access',
        {
          method: 'POST',
          body: JSON.stringify({ token })
        }
      );
      return response;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to access quiz';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Submit quiz response via token (public endpoint)
   */
  const submitQuizResponse = useCallback(async (
    submitData: MonthlyQuizSubmit
  ): Promise<{ success: boolean; message: string } | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.request<{ success: boolean; message: string }>(
        '/api/v2/monthly-quiz-public/submit',
        {
          method: 'POST',
          body: JSON.stringify(submitData)
        }
      );
      return response;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to submit quiz response';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    createQuizLink,
    createBulkQuizLinks,
    getQuizLinkStatus,
    getQuizStats,
    accessQuiz,
    submitQuizResponse
  };
}