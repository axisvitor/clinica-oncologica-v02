
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import Home from '@/app/page';
import { server, mockQuizSession, rest } from './mocks/server';
import { secureCookieAuth } from '@/lib/auth-utils';

// Mock the secureCookieAuth's checkSession method
jest.mock('@/lib/auth-utils', () => {
    const originalModule = jest.requireActual('@/lib/auth-utils');
    return {
        ...originalModule,
        secureCookieAuth: {
            ...originalModule.secureCookieAuth,
            checkSession: jest.fn().mockResolvedValue(false),
            initializeSession: jest.fn(originalModule.secureCookieAuth.initializeSession)
        },
    };
});


describe('Quiz Page Retry Logic', () => {
    const validToken = 'valid-token';
    const invalidToken = 'invalid-token';

    beforeEach(() => {
        // Reset mocks before each test
        jest.clearAllMocks();
        // Reset request handlers to their default state
        server.resetHandlers();
        // Mock checkSession to return false by default
        (secureCookieAuth.checkSession as jest.Mock).mockResolvedValue(false);
    });

    afterEach(() => {
        // Clean up after each test
        server.resetHandlers();
    });

    test('should show an error on initial load failure and successfully reload on retry', async () => {
        // Step 1: Mock the initial API call to fail
        let callCount = 0;
        (secureCookieAuth.initializeSession as jest.Mock).mockImplementation(async (token: string) => {
            callCount++;
            if (callCount === 1) {
                // First call fails
                throw new Error('Network error');
            }
            // Subsequent calls succeed
            if (token === validToken) {
                return Promise.resolve(mockQuizSession);
            }
            throw new Error('Invalid token');
        });

        // Initial render with the token in the URL
        window.history.pushState({}, 'Test page', `/?token=${validToken}`);
        render(<Home />);

        // Step 2: Verify that the error message is displayed
        await waitFor(() => {
            expect(screen.getByText(/Ops! Algo deu errado/i)).toBeInTheDocument();
        });
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();

        // Step 3: Simulate a user clicking the "Try Again" button
        const retryButton = screen.getByRole('button', { name: /Tentar Novamente/i });
        await userEvent.click(retryButton);

        // Step 4: Verify that the quiz interface is now visible after a successful retry
        await waitFor(() => {
            expect(screen.getByText(mockQuizSession.patient_name)).toBeInTheDocument();
            expect(screen.getByText(mockQuizSession.template_name)).toBeInTheDocument();
        }, { timeout: 3000 }); // Increased timeout for stability

        // Step 5: Assert that initializeSession was called twice
        expect(secureCookieAuth.initializeSession).toHaveBeenCalledTimes(2);
        // And that it was called with the same token both times
        expect(secureCookieAuth.initializeSession).toHaveBeenCalledWith(validToken);

    }, 10000); // 10-second timeout for the whole test
});
