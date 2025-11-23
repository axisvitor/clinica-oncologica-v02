/**
 * Test Data Factories Index
 * Central export for all test data factories
 */

export * from './patient.factory';
export * from './quiz.factory';
export * from './user.factory';

// Helper to reset all counters at once
export const resetAllFactories = () => {
  const { resetPatientCounter } = require('./patient.factory');
  const { resetQuizCounters } = require('./quiz.factory');
  const { resetUserCounter } = require('./user.factory');

  resetPatientCounter();
  resetQuizCounters();
  resetUserCounter();
};
