/**
 * Full Patient Journey E2E Tests
 * Verifies the flow from Doctor login -> Patient Registration -> System Tasks
 */

import { test, expect } from '@playwright/test';

test.describe('Full Patient Journey', () => {
    test.beforeEach(async ({ page }) => {
        // Login as Doctor
        await page.goto('/login');
        await page.fill('input[name="email"]', 'doctor@example.com');
        await page.fill('input[name="password"]', 'doctor123');
        await page.click('button[type="submit"]');
        await page.waitForURL('/dashboard');
    });

    test('should register patient and verify system tasks', async ({ page }) => {
        // 1. Navigate to patients page
        await page.goto('/patients');
        await page.waitForLoadState('networkidle');

        // 2. Open "Novo Paciente" dialog
        await page.click('button:has-text("Novo Paciente")');
        await page.waitForSelector('[role="dialog"]');

        // 3. Verify "Responsible Doctor" field is read-only and shows current user
        // Note: This assumes the logged-in user's name is "Dr. Doctor" or similar.
        // We check if the input is disabled/read-only.
        const doctorInput = page.locator('input[name="doctor_name"]'); // Assuming this is the field name for display
        if (await doctorInput.isVisible()) {
            await expect(doctorInput).toBeDisabled();
        } else {
            // If the field is hidden or different, we verify the select is not present/disabled
            const doctorSelect = page.locator('button:has-text("Selecione o médico")');
            await expect(doctorSelect).not.toBeVisible();
        }

        // 4. Fill patient form
        const timestamp = new Date().getTime();
        const patientName = `Patient Journey ${timestamp}`;
        await page.fill('input[name="nome"]', patientName);
        await page.fill('input[name="email"]', `patient${timestamp}@example.com`);
        await page.fill('input[name="telefone"]', '(11) 98888-7777');
        await page.fill('input[name="data_nascimento"]', '1990-01-01');
        await page.fill('input[name="cpf"]', '123.456.789-00'); // Mock CPF

        // Select cancer type
        await page.click('button:has-text("Selecione o tipo")');
        await page.click('text="Mama"');

        // Select treatment
        await page.click('button:has-text("Selecione o tratamento")');
        await page.click('text="Quimioterapia"');

        // 5. Submit form
        await page.click('button:has-text("Criar Paciente")');

        // 6. Verify success message
        await expect(page.locator('text="Paciente criado com sucesso"')).toBeVisible({
            timeout: 10000,
        });

        // 7. Verify patient appears in list
        await expect(page.locator(`text="${patientName}"`)).toBeVisible();

        // 8. Check Task Health Indicator (System Monitoring)
        // It should be present in the header
        const healthIndicator = page.locator('button:has(.lucide-activity)');
        await expect(healthIndicator).toBeVisible();

        // Click to open popover
        await healthIndicator.click();
        await expect(page.locator('text="System Tasks"')).toBeVisible();
        await expect(page.locator('text="Queue Status"')).toBeVisible();

        // 9. Navigate to patient details to check for tasks/messages (Optional)
        await page.click(`text="${patientName}"`);
        await page.waitForURL(/\/patients\/patient-/);

        // Check if "Messages" tab exists and click it
        const messagesTab = page.locator('button[role="tab"]:has-text("Mensagens")');
        if (await messagesTab.isVisible()) {
            await messagesTab.click();
            // We might expect a "Welcome" message or similar if the daily flow triggered immediately
            // await expect(page.locator('text="Olá"')).toBeVisible(); 
        }
    });
});
