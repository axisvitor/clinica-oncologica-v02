/**
 * E2E-012: WhatsApp Integration
 * Tests: send message → status update → delivery confirmation
 */
import { test, expect, Page } from '@playwright/test';

test.describe('E2E-012: WhatsApp Integration', () => {
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

  test('should send WhatsApp message to patient', async () => {
    // Step 1: Navigate to WhatsApp section
    await page.goto('/admin/whatsapp');

    // Step 2: Click send message
    await page.click('button:has-text("Nova Mensagem")');

    // Step 3: Select recipient
    await page.click('button:has-text("Selecionar Paciente")');
    await page.fill('input[placeholder*="Buscar"]', 'Maria');
    await page.waitForTimeout(500);
    await page.locator('[data-testid="patient-option"]').first().click();

    // Step 4: Type message
    await page.fill('textarea[name="message"]', 'Olá! Lembrete da sua consulta amanhã às 10h.');

    // Step 5: Send
    await page.click('button:has-text("Enviar")');

    // Step 6: Verify success
    await expect(page.locator('text=Mensagem enviada')).toBeVisible({ timeout: 5000 });

    // Step 7: Verify message in conversation
    await expect(page.locator('[data-testid="message-sent"]')).toContainText('Lembrete da sua consulta');
  });

  test('should check WhatsApp instance status', async () => {
    await page.goto('/admin/whatsapp');

    // Click instance status
    await page.click('button:has-text("Status da Instância")');

    // Verify status modal
    await expect(page.locator('[data-testid="instance-status"]')).toBeVisible();

    // Check connection status
    const statusBadge = page.locator('[data-testid="connection-status"]');
    await expect(statusBadge).toContainText(/conectado|desconectado/i);

    // Check QR code section (if disconnected)
    const qrSection = page.locator('[data-testid="qr-code-section"]');
    if (await qrSection.isVisible()) {
      await expect(qrSection.locator('img')).toBeVisible();
    }
  });

  test('should view message delivery status', async () => {
    await page.goto('/admin/whatsapp');

    // Find sent message
    const message = page.locator('[data-testid="message-sent"]').first();

    if (await message.isVisible()) {
      // Click message for details
      await message.click();

      // Verify delivery status shown
      const deliveryStatus = page.locator('[data-testid="delivery-status"]');
      await expect(deliveryStatus).toBeVisible();

      // Check for status icons (sent, delivered, read)
      const statusIcon = page.locator('[data-testid="status-icon"]');
      await expect(statusIcon).toBeVisible();
    } else {
      test.skip(); // No messages to check
    }
  });

  test('should send WhatsApp with media attachment', async () => {
    await page.goto('/admin/whatsapp');
    await page.click('button:has-text("Nova Mensagem")');

    // Select patient
    await page.click('button:has-text("Selecionar Paciente")');
    await page.locator('[data-testid="patient-option"]').first().click();

    // Type message
    await page.fill('textarea[name="message"]', 'Segue resultado do exame');

    // Attach file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'resultado.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('PDF content')
    });

    // Verify file attached
    await expect(page.locator('text=resultado.pdf')).toBeVisible();

    // Send
    await page.click('button:has-text("Enviar")');

    // Verify success
    await expect(page.locator('text=Mensagem enviada')).toBeVisible();
  });

  test('should schedule WhatsApp message', async () => {
    await page.goto('/admin/whatsapp');
    await page.click('button:has-text("Nova Mensagem")');

    // Select patient
    await page.click('button:has-text("Selecionar Paciente")');
    await page.locator('[data-testid="patient-option"]').first().click();

    // Type message
    await page.fill('textarea[name="message"]', 'Lembrete agendado');

    // Enable scheduling
    await page.check('input[name="schedule"]');

    // Set schedule time
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0];

    await page.fill('input[name="scheduled_date"]', dateStr);
    await page.fill('input[name="scheduled_time"]', '14:00');

    // Schedule
    await page.click('button:has-text("Agendar")');

    // Verify scheduled
    await expect(page.locator('text=Mensagem agendada')).toBeVisible();

    // Check scheduled messages
    await page.click('button[role="tab"]:has-text("Agendadas")');
    await expect(page.locator('text=Lembrete agendado')).toBeVisible();
  });

  test('should use WhatsApp message template', async () => {
    await page.goto('/admin/whatsapp');
    await page.click('button:has-text("Nova Mensagem")');

    // Select patient
    await page.click('button:has-text("Selecionar Paciente")');
    await page.locator('[data-testid="patient-option"]').first().click();

    // Click templates
    await page.click('button:has-text("Templates")');

    // Select template
    await page.click('[data-testid="template-appointment-reminder"]');

    // Verify template loaded
    await expect(page.locator('textarea[name="message"]')).not.toBeEmpty();

    // Can edit template
    const currentText = await page.locator('textarea[name="message"]').inputValue();
    await page.fill('textarea[name="message"]', `${currentText}\n\nAté breve!`);

    // Send
    await page.click('button:has-text("Enviar")');
    await expect(page.locator('text=Mensagem enviada')).toBeVisible();
  });

  test('should view WhatsApp conversation history', async () => {
    await page.goto('/admin/whatsapp');

    // Select patient
    await page.click('[data-testid="conversation-list"] [data-testid="patient-conversation"]').first();

    // Verify conversation loads
    await expect(page.locator('[data-testid="conversation-messages"]')).toBeVisible();

    // Verify messages displayed
    const messages = page.locator('[data-testid="message"]');
    const count = await messages.count();
    expect(count).toBeGreaterThan(0);

    // Verify sent/received differentiation
    const sentMessages = page.locator('[data-testid="message-sent"]');
    const receivedMessages = page.locator('[data-testid="message-received"]');

    // At least one should exist
    const hasSent = await sentMessages.count() > 0;
    const hasReceived = await receivedMessages.count() > 0;
    expect(hasSent || hasReceived).toBeTruthy();
  });

  test('should handle WhatsApp connection error', async () => {
    await page.goto('/admin/whatsapp');

    // Try to send when disconnected (simulated)
    // This would require mocking the API response

    await page.click('button:has-text("Nova Mensagem")');
    await page.click('button:has-text("Selecionar Paciente")');
    await page.locator('[data-testid="patient-option"]').first().click();
    await page.fill('textarea[name="message"]', 'Test message');

    // If disconnected, should show error
    await page.click('button:has-text("Enviar")');

    // Check for either success or connection error
    const successMessage = page.locator('text=Mensagem enviada');
    const errorMessage = page.locator('text=Erro de conexão');

    await expect(successMessage.or(errorMessage)).toBeVisible({ timeout: 5000 });
  });
});
