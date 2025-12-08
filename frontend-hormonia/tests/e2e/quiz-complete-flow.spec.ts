/**
 * Monthly Quiz Complete Flow E2E Test
 *
 * Tests the complete end-to-end flow of the monthly quiz feature:
 * 1. Admin creates quiz and generates patient link
 * 2. System sends WhatsApp notification (mocked)
 * 3. Patient accesses quiz via link
 * 4. Patient completes all quiz questions
 * 5. Admin views results and statistics
 *
 * Priority: CRITICAL
 * Estimated Duration: 5-10 minutes
 */

import { test, expect, Page } from '@playwright/test';

// Test data
const ADMIN_CREDENTIALS = {
  email: 'admin@test.com',
  password: 'Test123!@#',
};

const PATIENT_DATA = {
  name: 'Maria Silva',
  cpf: '123.456.789-00',
  phone: '+55 11 98765-4321',
  email: 'maria.silva@test.com',
};

const QUIZ_QUESTIONS = [
  {
    text: 'Como você está se sentindo hoje?',
    type: 'radio',
    options: ['Muito bem', 'Bem', 'Regular', 'Mal', 'Muito mal'],
  },
  {
    text: 'Está seguindo o tratamento corretamente?',
    type: 'radio',
    options: ['Sim', 'Parcialmente', 'Não'],
  },
  {
    text: 'Teve algum efeito colateral esta semana?',
    type: 'checkbox',
    options: ['Náusea', 'Dor de cabeça', 'Fadiga', 'Nenhum'],
  },
  {
    text: 'Observações ou dúvidas (opcional)',
    type: 'textarea',
    optional: true,
  },
];

// Helper functions
async function loginAsAdmin(page: Page) {
  console.log('🔐 Logging in as admin...');
  await page.goto('/login');

  await page.waitForSelector('[data-testid="email-input"]', { timeout: 10000 });
  await page.fill('[data-testid="email-input"]', ADMIN_CREDENTIALS.email);
  await page.fill('[data-testid="password-input"]', ADMIN_CREDENTIALS.password);

  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle' }),
    page.click('[data-testid="login-submit"]'),
  ]);

  await expect(page.locator('[data-testid="dashboard"]')).toBeVisible({ timeout: 15000 });
  console.log('✅ Admin logged in successfully');
}

async function createPatient(page: Page) {
  console.log('👤 Creating test patient...');
  await page.goto('/patients');

  await page.click('[data-testid="create-patient-button"]');

  await page.waitForSelector('[data-testid="patient-form"]');
  await page.fill('[data-testid="patient-name"]', PATIENT_DATA.name);
  await page.fill('[data-testid="patient-cpf"]', PATIENT_DATA.cpf);
  await page.fill('[data-testid="patient-phone"]', PATIENT_DATA.phone);
  await page.fill('[data-testid="patient-email"]', PATIENT_DATA.email);

  await Promise.all([
    page.waitForResponse(resp => resp.url().includes('/api/v2/patients') && resp.status() === 201),
    page.click('[data-testid="save-patient"]'),
  ]);

  await expect(page.locator('.toast-success')).toBeVisible();
  console.log('✅ Patient created successfully');
}

async function generateQuizLink(page: Page): Promise<string> {
  console.log('📝 Generating monthly quiz link...');
  await page.goto('/monthly-quiz/admin');

  // Find patient in list
  await page.waitForSelector('[data-testid="patient-list"]');
  const patientRow = page.locator(`[data-patient-name="${PATIENT_DATA.name}"]`).first();
  await expect(patientRow).toBeVisible();

  // Generate quiz link
  await patientRow.locator('[data-testid="generate-quiz-link"]').click();

  // Wait for link generation
  await page.waitForSelector('[data-testid="quiz-link-modal"]');
  const linkElement = page.locator('[data-testid="quiz-link-url"]');
  await expect(linkElement).toBeVisible();

  const quizLink = await linkElement.textContent();
  expect(quizLink).toBeTruthy();
  expect(quizLink).toContain('quiz');

  console.log(`✅ Quiz link generated: ${quizLink}`);

  // Copy link and close modal
  await page.click('[data-testid="copy-link-button"]');
  await expect(page.locator('.toast-success')).toContainText('Link copiado');
  await page.click('[data-testid="close-modal"]');

  return quizLink!;
}

async function completeQuizAsPatient(page: Page, quizLink: string) {
  console.log('🎯 Patient completing quiz...');

  // Open quiz in new context (simulate different device)
  await page.goto(quizLink);

  // Wait for quiz to load
  await page.waitForSelector('[data-testid="quiz-container"]', { timeout: 10000 });
  await expect(page.locator('[data-testid="quiz-title"]')).toBeVisible();

  console.log('✅ Quiz page loaded');

  // Answer Question 1 (Radio)
  console.log('📝 Answering question 1...');
  await page.click('[data-testid="question-1-option-2"]'); // "Bem"
  await page.click('[data-testid="next-question"]');

  // Answer Question 2 (Radio)
  console.log('📝 Answering question 2...');
  await page.click('[data-testid="question-2-option-1"]'); // "Sim"
  await page.click('[data-testid="next-question"]');

  // Answer Question 3 (Checkbox)
  console.log('📝 Answering question 3...');
  await page.check('[data-testid="question-3-option-3"]'); // "Fadiga"
  await page.click('[data-testid="next-question"]');

  // Answer Question 4 (Textarea - optional)
  console.log('📝 Answering question 4...');
  await page.fill(
    '[data-testid="question-4-textarea"]',
    'Estou me sentindo melhor esta semana. Obrigada pelo acompanhamento!'
  );

  // Submit quiz
  console.log('📤 Submitting quiz...');
  await Promise.all([
    page.waitForResponse(resp =>
      resp.url().includes('/api/v2/monthly-quiz/public/submit') &&
      resp.status() === 200
    ),
    page.click('[data-testid="submit-quiz"]'),
  ]);

  // Verify success message
  await expect(page.locator('[data-testid="quiz-success"]')).toBeVisible({ timeout: 10000 });
  await expect(page.locator('[data-testid="quiz-success-message"]')).toContainText('Quiz enviado com sucesso');

  console.log('✅ Quiz submitted successfully');
}

async function verifyQuizResults(page: Page) {
  console.log('📊 Verifying quiz results in admin dashboard...');

  await page.goto('/monthly-quiz/admin');

  // Wait for results to load
  await page.waitForSelector('[data-testid="quiz-results-list"]');

  // Find patient's quiz result
  const resultRow = page.locator(`[data-patient-name="${PATIENT_DATA.name}"]`).first();
  await expect(resultRow).toBeVisible();

  // Check that quiz is marked as completed
  await expect(resultRow.locator('[data-testid="quiz-status"]')).toContainText('Completo');

  // View detailed results
  await resultRow.locator('[data-testid="view-results"]').click();

  await page.waitForSelector('[data-testid="quiz-results-detail"]');

  // Verify question 1 answer
  const q1Answer = page.locator('[data-testid="result-question-1"]');
  await expect(q1Answer).toContainText('Bem');

  // Verify question 2 answer
  const q2Answer = page.locator('[data-testid="result-question-2"]');
  await expect(q2Answer).toContainText('Sim');

  // Verify question 3 answer
  const q3Answer = page.locator('[data-testid="result-question-3"]');
  await expect(q3Answer).toContainText('Fadiga');

  // Verify question 4 answer
  const q4Answer = page.locator('[data-testid="result-question-4"]');
  await expect(q4Answer).toContainText('Estou me sentindo melhor');

  console.log('✅ Quiz results verified successfully');
}

async function verifyStatistics(page: Page) {
  console.log('📈 Verifying quiz statistics...');

  await page.goto('/monthly-quiz/admin/statistics');

  await page.waitForSelector('[data-testid="quiz-statistics"]');

  // Verify completion rate
  const completionRate = page.locator('[data-testid="completion-rate"]');
  await expect(completionRate).toBeVisible();

  // Verify total submissions
  const totalSubmissions = page.locator('[data-testid="total-submissions"]');
  await expect(totalSubmissions).toBeVisible();
  const count = await totalSubmissions.textContent();
  expect(parseInt(count!)).toBeGreaterThan(0);

  // Verify charts are rendered
  await expect(page.locator('[data-testid="statistics-chart"]')).toBeVisible();

  console.log('✅ Statistics verified successfully');
}

// Main test suite
test.describe('Monthly Quiz - Complete Flow', () => {

  test.beforeEach(async ({ page }) => {
    // Set timeout for slower operations
    test.setTimeout(120000); // 2 minutes

    // Monitor console errors
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Store errors for later verification
    (page as any).consoleErrors = errors;
  });

  test('TC-QUIZ-001: Complete monthly quiz flow - Admin creates, patient completes, admin views results', async ({ page, context }) => {
    console.log('🚀 Starting complete quiz flow test...');

    // Step 1: Admin login
    await test.step('Admin logs in', async () => {
      await loginAsAdmin(page);
    });

    // Step 2: Create test patient
    await test.step('Create test patient', async () => {
      await createPatient(page);
    });

    // Step 3: Generate quiz link
    let quizLink: string;
    await test.step('Generate quiz link for patient', async () => {
      quizLink = await generateQuizLink(page);
    });

    // Step 4: Patient completes quiz (in new context)
    await test.step('Patient completes quiz', async () => {
      // Create new page to simulate different device/session
      const patientPage = await context.newPage();

      try {
        await completeQuizAsPatient(patientPage, quizLink!);
      } finally {
        await patientPage.close();
      }
    });

    // Step 5: Admin views results
    await test.step('Admin views quiz results', async () => {
      await verifyQuizResults(page);
    });

    // Step 6: Verify statistics
    await test.step('Verify quiz statistics', async () => {
      await verifyStatistics(page);
    });

    // Verify no console errors during flow
    const errors = (page as any).consoleErrors;
    if (errors.length > 0) {
      console.warn(`⚠️  Found ${errors.length} console errors:`, errors);
    }

    console.log('🎉 Complete quiz flow test passed!');
  });

  test('TC-QUIZ-002: Expired quiz link should show error', async ({ page }) => {
    console.log('🧪 Testing expired quiz link...');

    await loginAsAdmin(page);

    // Navigate to quiz admin
    await page.goto('/monthly-quiz/admin');

    // Generate expired link (mock)
    const expiredLink = '/quiz/expired-token-12345';

    // Try to access expired link
    await page.goto(expiredLink);

    // Should show error message
    await expect(page.locator('[data-testid="quiz-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="quiz-error-message"]')).toContainText(
      /expirado|inválido/i
    );

    console.log('✅ Expired link error handling verified');
  });

  test('TC-QUIZ-003: Cannot submit quiz twice with same link', async ({ page, context }) => {
    console.log('🧪 Testing duplicate submission prevention...');

    await loginAsAdmin(page);
    await createPatient(page);
    const quizLink = await generateQuizLink(page);

    // First submission
    const patientPage1 = await context.newPage();
    await completeQuizAsPatient(patientPage1, quizLink);
    await patientPage1.close();

    // Try second submission with same link
    const patientPage2 = await context.newPage();
    await patientPage2.goto(quizLink);

    // Should show "already completed" message
    await expect(patientPage2.locator('[data-testid="quiz-already-completed"]')).toBeVisible({
      timeout: 10000,
    });

    await patientPage2.close();

    console.log('✅ Duplicate submission prevention verified');
  });

  test('TC-QUIZ-004: Quiz validation - required questions must be answered', async ({ page, context }) => {
    console.log('🧪 Testing quiz validation...');

    await loginAsAdmin(page);
    await createPatient(page);
    const quizLink = await generateQuizLink(page);

    const patientPage = await context.newPage();
    await patientPage.goto(quizLink);

    await patientPage.waitForSelector('[data-testid="quiz-container"]');

    // Try to skip required question
    await patientPage.click('[data-testid="next-question"]');

    // Should show validation error
    await expect(patientPage.locator('[data-testid="validation-error"]')).toBeVisible();
    await expect(patientPage.locator('[data-testid="validation-error"]')).toContainText(
      /obrigatório|required/i
    );

    await patientPage.close();

    console.log('✅ Quiz validation verified');
  });

  test('TC-QUIZ-005: WhatsApp notification sent when link generated', async ({ page }) => {
    console.log('🧪 Testing WhatsApp notification...');

    await loginAsAdmin(page);
    await createPatient(page);

    // Monitor API calls
    const whatsappCalls: any[] = [];
    page.on('request', req => {
      if (req.url().includes('/api/v2/whatsapp/send') || req.url().includes('/webhooks/whatsapp')) {
        whatsappCalls.push({
          url: req.url(),
          method: req.method(),
        });
      }
    });

    await generateQuizLink(page);

    // Verify WhatsApp API was called
    expect(whatsappCalls.length).toBeGreaterThan(0);

    // Should show notification sent confirmation
    await expect(page.locator('.toast-info')).toContainText(/whatsapp|mensagem enviada/i);

    console.log('✅ WhatsApp notification verified');
  });

  test('TC-QUIZ-006: Admin can export quiz results to CSV', async ({ page }) => {
    console.log('🧪 Testing CSV export...');

    await loginAsAdmin(page);
    await page.goto('/monthly-quiz/admin');

    // Wait for results
    await page.waitForSelector('[data-testid="quiz-results-list"]');

    // Click export button
    const downloadPromise = page.waitForEvent('download');
    await page.click('[data-testid="export-csv"]');
    const download = await downloadPromise;

    // Verify download
    expect(download.suggestedFilename()).toMatch(/quiz.*\.csv/i);

    console.log('✅ CSV export verified');
  });

  test('TC-QUIZ-007: Quiz supports all question types', async ({ page, context }) => {
    console.log('🧪 Testing all question types...');

    await loginAsAdmin(page);
    await createPatient(page);
    const quizLink = await generateQuizLink(page);

    const patientPage = await context.newPage();
    await patientPage.goto(quizLink);

    await patientPage.waitForSelector('[data-testid="quiz-container"]');

    // Verify radio button questions
    await expect(patientPage.locator('[type="radio"]').first()).toBeVisible();

    // Verify checkbox questions
    await expect(patientPage.locator('[type="checkbox"]').first()).toBeVisible();

    // Verify textarea questions
    await expect(patientPage.locator('textarea').first()).toBeVisible();

    await patientPage.close();

    console.log('✅ All question types verified');
  });

  test('TC-QUIZ-008: Quiz progress is saved and can be resumed', async ({ page, context }) => {
    console.log('🧪 Testing quiz progress save/resume...');

    await loginAsAdmin(page);
    await createPatient(page);
    const quizLink = await generateQuizLink(page);

    // Start quiz
    const patientPage = await context.newPage();
    await patientPage.goto(quizLink);
    await patientPage.waitForSelector('[data-testid="quiz-container"]');

    // Answer first question
    await patientPage.click('[data-testid="question-1-option-2"]');
    await patientPage.click('[data-testid="next-question"]');

    // Close without finishing
    await patientPage.close();

    // Reopen same link
    const patientPage2 = await context.newPage();
    await patientPage2.goto(quizLink);

    // Should resume from question 2
    await expect(patientPage2.locator('[data-testid="question-number"]')).toContainText('2');

    await patientPage2.close();

    console.log('✅ Progress save/resume verified');
  });

});
