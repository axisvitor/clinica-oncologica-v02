/**
 * E2E-008: Patient Management
 * Tests: patient creation → quiz assignment → response view
 */
import { test, expect, Page } from '@playwright/test';

test.describe('E2E-008: Patient Management', () => {
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();

    // Login as admin
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'admin@test.com');
    await page.fill('input[name="password"]', 'Test@1234');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin/dashboard');

    // Navigate to patients
    await page.goto('/admin/patients');
  });

  test.afterEach(async () => {
    await page.close();
  });

  test('should create new patient successfully', async () => {
    // Step 1: Click create patient button
    await page.click('button:has-text("Novo Paciente")');

    // Step 2: Fill patient form
    await page.fill('input[name="name"]', 'Ana Paula Costa');
    await page.fill('input[name="email"]', `ana.${Date.now()}@test.com`);
    await page.fill('input[name="phone"]', '+5511987654321');
    await page.fill('input[name="cpf"]', '123.456.789-10');
    await page.fill('input[name="birth_date"]', '1988-03-25');
    await page.selectOption('select[name="gender"]', 'F');

    // Step 3: Submit form
    await page.click('button[type="submit"]');

    // Step 4: Verify success message
    await expect(page.locator('text=Paciente criado com sucesso')).toBeVisible({ timeout: 5000 });

    // Step 5: Verify patient in list
    await page.waitForTimeout(1000);
    await expect(page.locator('text=Ana Paula Costa')).toBeVisible();
  });

  test('should assign quiz to patient', async () => {
    // Step 1: Select first patient
    const firstPatient = page.locator('tbody tr').first();
    await firstPatient.click();

    // Step 2: Open quiz assignment
    await page.click('button:has-text("Enviar Quiz")');

    // Step 3: Select quiz template
    await page.selectOption('select[name="template_id"]', '1');

    // Step 4: Choose delivery method
    await page.check('input[value="whatsapp"]');

    // Step 5: Send quiz
    await page.click('button:has-text("Enviar")');

    // Step 6: Verify success
    await expect(page.locator('text=Quiz enviado')).toBeVisible();

    // Step 7: Verify quiz appears in patient timeline
    await expect(page.locator('[data-testid="patient-timeline"]')).toContainText('Quiz enviado');
  });

  test('should view patient quiz responses', async () => {
    // Step 1: Find patient with completed quiz
    await page.fill('input[placeholder*="Buscar"]', 'Maria');
    await page.waitForTimeout(500);

    // Step 2: Click patient
    await page.locator('tbody tr').first().click();

    // Step 3: Navigate to quiz responses tab
    await page.click('button[role="tab"]:has-text("Respostas")');

    // Step 4: Verify responses visible
    await expect(page.locator('[data-testid="quiz-responses"]')).toBeVisible();

    // Step 5: View specific response
    const firstResponse = page.locator('[data-testid="quiz-response-card"]').first();
    await firstResponse.click();

    // Step 6: Verify response details
    await expect(page.locator('[data-testid="response-details"]')).toBeVisible();
    await expect(page.locator('text=Pergunta')).toBeVisible();
    await expect(page.locator('text=Resposta')).toBeVisible();
  });

  test('should edit patient information', async () => {
    // Step 1: Select patient
    const firstPatient = page.locator('tbody tr').first();
    const originalName = await firstPatient.locator('td').nth(1).textContent();
    await firstPatient.click();

    // Step 2: Click edit button
    await page.click('button:has-text("Editar")');

    // Step 3: Update phone number
    const newPhone = '+5511999999999';
    await page.fill('input[name="phone"]', newPhone);

    // Step 4: Save changes
    await page.click('button:has-text("Salvar")');

    // Step 5: Verify success
    await expect(page.locator('text=Atualizado com sucesso')).toBeVisible();

    // Step 6: Verify phone updated
    await expect(page.locator(`text=${newPhone}`)).toBeVisible();
  });

  test('should deactivate patient', async () => {
    // Step 1: Select patient
    const firstPatient = page.locator('tbody tr').first();
    await firstPatient.click();

    // Step 2: Open actions menu
    await page.click('[data-testid="patient-actions-menu"]');

    // Step 3: Click deactivate
    await page.click('button:has-text("Desativar")');

    // Step 4: Confirm action
    await page.click('button:has-text("Confirmar")');

    // Step 5: Verify success
    await expect(page.locator('text=Paciente desativado')).toBeVisible();

    // Step 6: Verify status badge
    await expect(page.locator('[data-testid="patient-status"]')).toContainText('Inativo');
  });

  test('should filter patients by status', async () => {
    // Step 1: Open filters
    await page.click('button:has-text("Filtros")');

    // Step 2: Select active patients only
    await page.check('input[name="status"][value="active"]');

    // Step 3: Apply filters
    await page.click('button:has-text("Aplicar")');

    // Step 4: Verify filtered results
    await page.waitForTimeout(500);
    const rows = page.locator('tbody tr');
    const count = await rows.count();

    // All visible patients should be active
    for (let i = 0; i < count; i++) {
      const statusBadge = rows.nth(i).locator('[data-testid="status-badge"]');
      await expect(statusBadge).toContainText('Ativo');
    }
  });

  test('should export patient data', async () => {
    // Step 1: Select patients
    await page.check('tbody tr:nth-child(1) input[type="checkbox"]');
    await page.check('tbody tr:nth-child(2) input[type="checkbox"]');

    // Step 2: Click export button
    const downloadPromise = page.waitForEvent('download');
    await page.click('button:has-text("Exportar")');

    // Step 3: Verify download started
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/pacientes.*\.csv/);
  });
});
