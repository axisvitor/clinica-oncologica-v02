/**
 * Monthly Quiz Hook for Frontend
 *
 * React hook for managing monthly quiz via link functionality.
 */
import { useState, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';
import {
  MonthlyQuizLinkCreate,
  MonthlyQuizLink,
  MonthlyQuizAccessRequest,
  MonthlyQuizAccess,
  MonthlyQuizSubmit,
  MonthlyQuizStats,
  BulkQuizLinkCreate,
  BulkQuizLinkResponse
} from '../types';

export function useMonthlyQuiz() {
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
    } catch (err: any) {
      setError(err.message || 'Failed to create quiz link');
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
    } catch (err: any) {
      setError(err.message || 'Failed to create bulk quiz links');
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
  ): Promise<MonthlyQuizLink | null> => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.monthlyQuiz.getStatus(sessionId);
      return response;
    } catch (err: any) {
      setError(err.message || 'Failed to get quiz link status');
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
    } catch (err: any) {
      setError(err.message || 'Failed to get quiz statistics');
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
        '/api/v1/monthly-quiz-public/access',
        {
          method: 'POST',
          body: JSON.stringify({ token })
        }
      );
      return response;
    } catch (err: any) {
      setError(err.message || 'Failed to access quiz');
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
        '/api/v1/monthly-quiz-public/submit',
        {
          method: 'POST',
          body: JSON.stringify(submitData)
        }
      );
      return response;
    } catch (err: any) {
      setError(err.message || 'Failed to submit quiz response');
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