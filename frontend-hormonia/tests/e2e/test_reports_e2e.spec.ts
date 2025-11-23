/**
 * E2E-011: Report Generation
 * Tests: report generation → PDF export → download
 */
import { test, expect, Page } from '@playwright/test';

test.describe('E2E-011: Report Generation', () => {
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    page = await browser.newPage();

    // Login
    await page.goto('/admin/login');
    await page.fill('input[name="email"]', 'admin@test.com');
    await page.fill('input[name="password"]', 'Test@1234');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/admin/dashboard');
  });

  test.afterEach(async () => {
    await page.close();
  });

  test('should generate patient monthly report', async () => {
    // Step 1: Navigate to patient
    await page.goto('/admin/patients');
    await page.locator('tbody tr').first().click();

    // Step 2: Go to reports tab
    await page.click('button[role="tab"]:has-text("Relatórios")');

    // Step 3: Click generate report
    await page.click('button:has-text("Gerar Relatório")');

    // Step 4: Select report type
    await page.selectOption('select[name="report_type"]', 'monthly_summary');

    // Step 5: Select month
    const currentMonth = new Date().toISOString().slice(0, 7); // YYYY-MM
    await page.fill('input[name="month"]', currentMonth);

    // Step 6: Generate
    await page.click('button:has-text("Gerar")');

    // Step 7: Wait for generation (may be async)
    await expect(page.locator('text=Relatório gerado')).toBeVisible({ timeout: 15000 });

    // Step 8: Verify report preview
    await expect(page.locator('[data-testid="report-preview"]')).toBeVisible();

    // Step 9: Verify report content
    await expect(page.locator('[data-testid="report-content"]')).toContainText('Resumo Mensal');
  });

  test('should export report as PDF', async () => {
    await page.goto('/admin/patients');
    await page.locator('tbody tr').first().click();
    await page.click('button[role="tab"]:has-text("Relatórios")');

    // Find existing report or generate one
    const existingReport = page.locator('[data-testid="report-card"]').first();

    if (await existingReport.isVisible()) {
      // Click export PDF
      const downloadPromise = page.waitForEvent('download');
      await existingReport.locator('button:has-text("Exportar PDF")').click();

      // Verify download
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/\.pdf$/);
    } else {
      // Generate new report first
      await page.click('button:has-text("Gerar Relatório")');
      await page.selectOption('select[name="report_type"]', 'monthly_summary');
      await page.click('button:has-text("Gerar")');

      await expect(page.locator('text=Relatório gerado')).toBeVisible({ timeout: 15000 });

      // Now export
      const downloadPromise = page.waitForEvent('download');
      await page.click('button:has-text("Exportar PDF")');

      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/\.pdf$/);
    }
  });

  test('should generate system-wide analytics report', async () => {
    // Navigate to reports section
    await page.goto('/admin/reports');

    // Click generate analytics
    await page.click('button:has-text("Relatório Analítico")');

    // Select date range
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    await page.fill('input[name="start_date"]', startDate);
    await page.fill('input[name="end_date"]', endDate);

    // Generate
    await page.click('button:has-text("Gerar")');

    // Wait for report
    await expect(page.locator('[data-testid="analytics-report"]')).toBeVisible({ timeout: 15000 });

    // Verify key metrics present
    await expect(page.locator('text=Total de Pacientes')).toBeVisible();
    await expect(page.locator('text=Quizzes Completados')).toBeVisible();
    await expect(page.locator('text=Taxa de Adesão')).toBeVisible();
  });

  test('should schedule automated report', async () => {
    await page.goto('/admin/reports');

    // Click schedule report
    await page.click('button:has-text("Agendar Relatório")');

    // Configure schedule
    await page.selectOption('select[name="report_type"]', 'weekly_summary');
    await page.selectOption('select[name="frequency"]', 'weekly');
    await page.selectOption('select[name="day_of_week"]', '1'); // Monday
    await page.fill('input[name="time"]', '09:00');

    // Select recipients
    await page.fill('input[name="recipients"]', 'admin@test.com, medico@test.com');

    // Save schedule
    await page.click('button:has-text("Salvar Agendamento")');

    // Verify success
    await expect(page.locator('text=Relatório agendado')).toBeVisible();

    // Verify in scheduled list
    await page.click('button[role="tab"]:has-text("Agendados")');
    await expect(page.locator('text=Resumo Semanal')).toBeVisible();
  });

  test('should customize report filters', async () => {
    await page.goto('/admin/reports');
    await page.click('button:has-text("Novo Relatório")');

    // Select custom report
    await page.selectOption('select[name="report_type"]', 'custom');

    // Apply filters
    await page.click('button:has-text("Filtros Avançados")');

    // Filter by treatment type
    await page.check('input[name="treatment_type"][value="Hormonal"]');

    // Filter by age range
    await page.fill('input[name="age_min"]', '30');
    await page.fill('input[name="age_max"]', '60');

    // Filter by status
    await page.check('input[name="status"][value="active"]');

    // Apply and generate
    await page.click('button:has-text("Aplicar Filtros")');
    await page.click('button:has-text("Gerar")');

    // Verify filtered report
    await expect(page.locator('[data-testid="report-filters-summary"]')).toBeVisible();
    await expect(page.locator('text=Hormonal')).toBeVisible();
  });

  test('should preview report before export', async () => {
    await page.goto('/admin/patients');
    await page.locator('tbody tr').first().click();
    await page.click('button[role="tab"]:has-text("Relatórios")');

    await page.click('button:has-text("Gerar Relatório")');
    await page.selectOption('select[name="report_type"]', 'monthly_summary');
    await page.click('button:has-text("Gerar")');

    await page.waitForSelector('[data-testid="report-preview"]', { timeout: 15000 });

    // Verify preview sections
    await expect(page.locator('h2:has-text("Informações do Paciente")')).toBeVisible();
    await expect(page.locator('h2:has-text("Respostas de Quizzes")')).toBeVisible();
    await expect(page.locator('h2:has-text("Análise de Adesão")')).toBeVisible();

    // Verify can scroll through preview
    const preview = page.locator('[data-testid="report-preview"]');
    await preview.evaluate(el => el.scrollTop = el.scrollHeight / 2);
  });

  test('should share report via email', async () => {
    await page.goto('/admin/reports');

    const reportCard = page.locator('[data-testid="report-card"]').first();

    if (await reportCard.isVisible()) {
      // Click share button
      await reportCard.locator('button:has-text("Compartilhar")').click();

      // Enter email
      await page.fill('input[name="recipient_email"]', 'medico@example.com');

      // Add message
      await page.fill('textarea[name="message"]', 'Segue relatório solicitado');

      // Send
      await page.click('button:has-text("Enviar")');

      // Verify success
      await expect(page.locator('text=Relatório enviado')).toBeVisible();
    } else {
      test.skip(); // No reports available
    }
  });
});
