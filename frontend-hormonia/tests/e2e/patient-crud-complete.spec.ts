/**
 * Patient CRUD E2E Tests
 * Comprehensive tests for patient create, read, update, delete operations
 */

import { test, expect } from '@playwright/test';

test.describe('Patient CRUD Operations', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[name="email"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });

  test('should create a new patient successfully', async ({ page }) => {
    // Navigate to patients page
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Click create patient button
    await page.click('button:has-text("Novo Paciente")');
    await page.waitForSelector('[role="dialog"]');

    // Fill patient form
    await page.fill('input[name="nome"]', 'Maria Santos Silva');
    await page.fill('input[name="email"]', 'maria.santos@example.com');
    await page.fill('input[name="telefone"]', '(11) 91234-5678');
    await page.fill('input[name="data_nascimento"]', '1985-03-20');
    await page.fill('input[name="cpf"]', '987.654.321-00');

    // Select cancer type
    await page.click('button:has-text("Selecione o tipo")');
    await page.click('text="Mama"');

    // Select treatment
    await page.click('button:has-text("Selecione o tratamento")');
    await page.click('text="Quimioterapia"');

    // Submit form
    await page.click('button:has-text("Criar Paciente")');

    // Verify success message
    await expect(page.locator('text="Paciente criado com sucesso"')).toBeVisible({
      timeout: 5000,
    });

    // Verify patient appears in list
    await expect(page.locator('text="Maria Santos Silva"')).toBeVisible();
  });

  test('should read and display patient details', async ({ page }) => {
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Click on first patient
    const firstPatient = page.locator('tr[data-testid^="patient-row"]').first();
    await firstPatient.click();

    // Wait for patient details page
    await page.waitForURL(/\/patients\/patient-\d+/);

    // Verify patient details are displayed
    await expect(page.locator('h1')).toContainText('Detalhes do Paciente');
    await expect(page.locator('text="Nome:"')).toBeVisible();
    await expect(page.locator('text="Email:"')).toBeVisible();
    await expect(page.locator('text="Telefone:"')).toBeVisible();
    await expect(page.locator('text="Tipo de Câncer:"')).toBeVisible();
  });

  test('should update patient information', async ({ page }) => {
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Click edit on first patient
    const editButton = page.locator('button[aria-label="Editar paciente"]').first();
    await editButton.click();
    await page.waitForSelector('[role="dialog"]');

    // Update patient name
    const nameInput = page.locator('input[name="nome"]');
    await nameInput.clear();
    await nameInput.fill('Maria Santos Silva Atualizada');

    // Update phone
    const phoneInput = page.locator('input[name="telefone"]');
    await phoneInput.clear();
    await phoneInput.fill('(11) 99999-8888');

    // Save changes
    await page.click('button:has-text("Salvar Alterações")');

    // Verify success message
    await expect(page.locator('text="Paciente atualizado com sucesso"')).toBeVisible({
      timeout: 5000,
    });

    // Verify updated information
    await expect(page.locator('text="Maria Santos Silva Atualizada"')).toBeVisible();
    await expect(page.locator('text="(11) 99999-8888"')).toBeVisible();
  });

  test('should delete patient with confirmation', async ({ page }) => {
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Get initial patient count
    const initialCount = await page.locator('tr[data-testid^="patient-row"]').count();

    // Click delete on first patient
    const deleteButton = page.locator('button[aria-label="Excluir paciente"]').first();
    await deleteButton.click();

    // Confirm deletion
    await page.waitForSelector('[role="alertdialog"]');
    await expect(page.locator('text="Tem certeza que deseja excluir"')).toBeVisible();
    await page.click('button:has-text("Confirmar")');

    // Verify success message
    await expect(page.locator('text="Paciente excluído com sucesso"')).toBeVisible({
      timeout: 5000,
    });

    // Verify patient count decreased
    const newCount = await page.locator('tr[data-testid^="patient-row"]').count();
    expect(newCount).toBe(initialCount - 1);
  });

  test('should validate required fields on create', async ({ page }) => {
    await page.goto('/patients');
    await page.click('button:has-text("Novo Paciente")');
    await page.waitForSelector('[role="dialog"]');

    // Try to submit without filling required fields
    await page.click('button:has-text("Criar Paciente")');

    // Verify validation errors
    await expect(page.locator('text="Nome é obrigatório"')).toBeVisible();
    await expect(page.locator('text="Email é obrigatório"')).toBeVisible();
    await expect(page.locator('text="CPF é obrigatório"')).toBeVisible();
  });

  test('should filter patients by name', async ({ page }) => {
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Enter search term
    await page.fill('input[placeholder*="Buscar"]', 'Maria');
    await page.waitForTimeout(500); // Debounce

    // Verify filtered results
    const visiblePatients = page.locator('tr[data-testid^="patient-row"]');
    await expect(visiblePatients.first()).toContainText('Maria');
  });

  test('should paginate patient list', async ({ page }) => {
    await page.goto('/patients');
    await page.waitForLoadState('networkidle');

    // Check if pagination exists
    const pagination = page.locator('[aria-label="Paginação"]');
    if (await pagination.isVisible()) {
      // Click next page
      await page.click('button[aria-label="Próxima página"]');
      await page.waitForLoadState('networkidle');

      // Verify URL changed
      await expect(page).toHaveURL(/page=2/);
    }
  });

  test('should handle concurrent patient creation', async ({ page }) => {
    await page.goto('/patients');

    // Create first patient
    await page.click('button:has-text("Novo Paciente")');
    await page.fill('input[name="nome"]', 'Paciente Teste 1');
    await page.fill('input[name="email"]', 'teste1@example.com');
    await page.fill('input[name="cpf"]', '111.222.333-44');
    await page.click('button:has-text("Criar Paciente")');
    await expect(page.locator('text="Paciente criado com sucesso"')).toBeVisible();

    // Create second patient immediately
    await page.click('button:has-text("Novo Paciente")');
    await page.fill('input[name="nome"]', 'Paciente Teste 2');
    await page.fill('input[name="email"]', 'teste2@example.com');
    await page.fill('input[name="cpf"]', '555.666.777-88');
    await page.click('button:has-text("Criar Paciente")');
    await expect(page.locator('text="Paciente criado com sucesso"')).toBeVisible();

    // Verify both patients are in list
    await expect(page.locator('text="Paciente Teste 1"')).toBeVisible();
    await expect(page.locator('text="Paciente Teste 2"')).toBeVisible();
  });
});
