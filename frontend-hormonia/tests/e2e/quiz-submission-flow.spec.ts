/**
 * Quiz Submission Flow E2E Tests
 * Tests complete quiz submission workflow from start to finish
 */

import { test, expect } from '@playwright/test';

test.describe('Quiz Submission Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin
    await page.goto('/login');
    await page.fill('input[name="email"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });

  test('should send quiz link to patient', async ({ page }) => {
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Click on patient
    const firstPatient = page.locator('tr[data-testid^="patient-row"]').first();
    await firstPatient.click();

    // Send quiz link
    await page.click('button:has-text("Enviar Questionário")');
    await page.waitForSelector('[role="dialog"]');

    // Select quiz template
    await page.click('button:has-text("Selecione o questionário")');
    await page.click('text="Avaliação Mensal"');

    // Send link
    await page.click('button:has-text("Enviar Link")');

    // Verify success
    await expect(page.locator('text="Link enviado com sucesso"')).toBeVisible();
  });

  test('should complete full quiz submission', async ({ page, context }) => {
    // Get quiz link from patient page
    await page.goto('/patients/patient-1');
    await page.click('button:has-text("Gerar Link do Quiz")');
    await page.waitForSelector('[role="dialog"]');

    // Copy quiz link
    const quizLink = await page.locator('input[readonly]').inputValue();
    expect(quizLink).toContain('/quiz/');

    // Open quiz in new tab (simulate patient receiving link)
    const quizPage = await context.newPage();
    await quizPage.goto(quizLink);

    // Verify quiz loaded
    await expect(quizPage.locator('h1')).toContainText('Questionário');

    // Answer first question (multiple choice)
    await quizPage.click('input[type="checkbox"][value="Opção 1"]');
    await quizPage.click('input[type="checkbox"][value="Opção 2"]');
    await quizPage.click('button:has-text("Próxima")');

    // Answer second question (scale)
    await quizPage.click('input[type="radio"][value="7"]');
    await quizPage.click('button:has-text("Próxima")');

    // Answer third question (yes/no)
    await quizPage.click('input[type="radio"][value="sim"]');
    await quizPage.click('button:has-text("Próxima")');

    // Answer fourth question (text)
    await quizPage.fill('textarea', 'Estou me sentindo melhor esta semana');
    await quizPage.click('button:has-text("Finalizar")');

    // Verify completion
    await expect(quizPage.locator('text="Questionário concluído"')).toBeVisible();
    await expect(quizPage.locator('text="Obrigado"')).toBeVisible();

    // Verify in admin panel
    await page.goto('/patients/patient-1');
    await expect(page.locator('text="Quiz concluído"')).toBeVisible();
  });

  test('should save quiz progress and allow resume', async ({ page, context }) => {
    // Get quiz link
    await page.goto('/patients/patient-1');
    await page.click('button:has-text("Gerar Link do Quiz")');
    const quizLink = await page.locator('input[readonly]').inputValue();

    // Start quiz
    const quizPage = await context.newPage();
    await quizPage.goto(quizLink);

    // Answer first two questions
    await quizPage.click('input[type="checkbox"][value="Opção 1"]');
    await quizPage.click('button:has-text("Próxima")');
    await quizPage.click('input[type="radio"][value="5"]');
    await quizPage.click('button:has-text("Próxima")');

    // Close and reopen (simulate closing browser)
    await quizPage.close();
    const newQuizPage = await context.newPage();
    await newQuizPage.goto(quizLink);

    // Should show resume dialog
    await expect(newQuizPage.locator('text="Continuar de onde parou"')).toBeVisible();
    await newQuizPage.click('button:has-text("Continuar")');

    // Should be on question 3
    await expect(newQuizPage.locator('text="Pergunta 3"')).toBeVisible();

    // Verify previous answers preserved
    const progress = await newQuizPage.locator('[role="progressbar"]').getAttribute('aria-valuenow');
    expect(Number(progress)).toBeGreaterThan(40);
  });

  test('should validate required questions', async ({ page, context }) => {
    await page.goto('/patients/patient-1');
    await page.click('button:has-text("Gerar Link do Quiz")');
    const quizLink = await page.locator('input[readonly]').inputValue();

    const quizPage = await context.newPage();
    await quizPage.goto(quizLink);

    // Try to proceed without answering required question
    await quizPage.click('button:has-text("Próxima")');

    // Verify validation error
    await expect(quizPage.locator('text="Esta pergunta é obrigatória"')).toBeVisible();
  });

  test('should handle quiz expiration', async ({ page, context }) => {
    // Create expired quiz link (mock scenario)
    await page.goto('/patients/patient-1');
    await page.click('button:has-text("Gerar Link do Quiz")');

    // Get expired link from test data
    const expiredLink = 'http://localhost:3000/quiz/expired-session-123';

    const quizPage = await context.newPage();
    await quizPage.goto(expiredLink);

    // Verify expiration message
    await expect(quizPage.locator('text="Este questionário expirou"')).toBeVisible();
    await expect(quizPage.locator('text="Entre em contato"')).toBeVisible();
  });

  test('should show real-time progress indicator', async ({ page, context }) => {
    await page.goto('/patients/patient-1');
    await page.click('button:has-text("Gerar Link do Quiz")');
    const quizLink = await page.locator('input[readonly]').inputValue();

    const quizPage = await context.newPage();
    await quizPage.goto(quizLink);

    // Verify initial progress
    let progress = await quizPage.locator('[role="progressbar"]').getAttribute('aria-valuenow');
    expect(Number(progress)).toBe(0);

    // Answer first question
    await quizPage.click('input[type="checkbox"][value="Opção 1"]');
    await quizPage.click('button:has-text("Próxima")');

    // Verify progress increased
    progress = await quizPage.locator('[role="progressbar"]').getAttribute('aria-valuenow');
    expect(Number(progress)).toBeGreaterThan(20);

    // Verify question counter
    await expect(quizPage.locator('text="2 de 4"')).toBeVisible();
  });

  test('should allow navigation between questions', async ({ page, context }) => {
    await page.goto('/patients/patient-1');
    await page.click('button:has-text("Gerar Link do Quiz")');
    const quizLink = await page.locator('input[readonly]').inputValue();

    const quizPage = await context.newPage();
    await quizPage.goto(quizLink);

    // Go to question 2
    await quizPage.click('input[type="checkbox"][value="Opção 1"]');
    await quizPage.click('button:has-text("Próxima")');

    // Go back to question 1
    await quizPage.click('button:has-text("Anterior")');
    await expect(quizPage.locator('text="Pergunta 1"')).toBeVisible();

    // Verify previous answer is preserved
    const checkbox = quizPage.locator('input[type="checkbox"][value="Opção 1"]');
    await expect(checkbox).toBeChecked();
  });

  test('should handle network errors gracefully', async ({ page, context }) => {
    await page.goto('/patients/patient-1');
    await page.click('button:has-text("Gerar Link do Quiz")');
    const quizLink = await page.locator('input[readonly]').inputValue();

    const quizPage = await context.newPage();
    await quizPage.goto(quizLink);

    // Simulate network offline
    await context.setOffline(true);

    // Try to submit answer
    await quizPage.click('input[type="checkbox"][value="Opção 1"]');
    await quizPage.click('button:has-text("Próxima")');

    // Verify error message
    await expect(quizPage.locator('text="Erro de conexão"')).toBeVisible();
    await expect(quizPage.locator('text="Tente novamente"')).toBeVisible();

    // Restore network
    await context.setOffline(false);

    // Retry should work
    await quizPage.click('button:has-text("Tentar novamente")');
    await expect(quizPage.locator('text="Pergunta 2"')).toBeVisible();
  });
});
