import { test, expect } from '@playwright/test'

test.describe('Patient Management Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Assume user is already authenticated from global setup
    await page.goto('/patients')
  })

  test.describe('Patient List', () => {
    test('should display patient list correctly', async ({ page }) => {
      await expect(page.getByRole('heading', { name: /pacientes/i })).toBeVisible()

      // Should have a table or grid of patients
      await expect(page.getByTestId('patients-table').or(
        page.getByTestId('patients-grid')
      )).toBeVisible()

      // Should have create patient button
      await expect(page.getByRole('button', { name: /novo paciente/i })).toBeVisible()
    })

    test('should filter patients by status', async ({ page }) => {
      // Open status filter
      const statusFilter = page.getByTestId('status-filter').or(
        page.getByLabel(/filtrar por status/i)
      )

      if (await statusFilter.isVisible()) {
        await statusFilter.click()

        // Select active patients
        await page.getByRole('option', { name: /ativo/i }).click()

        // Verify URL contains filter
        await expect(page).toHaveURL(/.*status=active.*/)

        // Verify only active patients are shown
        const patientCards = page.getByTestId('patient-card')
        const count = await patientCards.count()

        if (count > 0) {
          // Check that all visible patients are active
          for (let i = 0; i < Math.min(count, 5); i++) {
            const statusBadge = patientCards.nth(i).getByTestId('status-badge')
            await expect(statusBadge).toHaveText(/ativo/i)
          }
        }
      }
    })

    test('should search patients by name', async ({ page }) => {
      const searchInput = page.getByPlaceholder(/buscar pacientes/i).or(
        page.getByRole('searchbox')
      )

      await searchInput.fill('João')
      await page.keyboard.press('Enter')

      // Should filter results
      await expect(page).toHaveURL(/.*search=.*Jo.*o.*/)

      // Check if results contain search term (if any results exist)
      const patientCards = page.getByTestId('patient-card')
      const count = await patientCards.count()

      if (count > 0) {
        const firstPatient = patientCards.first()
        await expect(firstPatient).toContainText(/joão/i)
      } else {
        // Should show "no results" message
        await expect(page.getByText(/nenhum paciente encontrado/i)).toBeVisible()
      }
    })

    test('should paginate patient list', async ({ page }) => {
      const paginationContainer = page.getByTestId('pagination').or(
        page.getByRole('navigation', { name: /paginação/i })
      )

      if (await paginationContainer.isVisible()) {
        const nextButton = page.getByRole('button', { name: /próxima/i }).or(
          page.getByTestId('next-page')
        )

        if (await nextButton.isEnabled()) {
          await nextButton.click()

          // Should navigate to next page
          await expect(page).toHaveURL(/.*page=2.*/)

          // Should load new patients
          await expect(page.getByTestId('patients-table')).toBeVisible()
        }
      }
    })
  })

  test.describe('Create Patient', () => {
    test('should create new patient successfully', async ({ page }) => {
      // Open create patient dialog
      await page.getByRole('button', { name: /novo paciente/i }).click()

      // Verify dialog is open
      await expect(page.getByRole('dialog')).toBeVisible()
      await expect(page.getByText(/novo paciente/i)).toBeVisible()

      // Fill form
      await page.getByLabel(/nome completo/i).fill('Maria da Silva')
      await page.getByLabel(/email/i).fill('maria@example.com')
      await page.getByLabel(/telefone/i).fill('11999999999')
      await page.getByLabel(/data de nascimento/i).fill('1985-03-15')

      // Select gender
      await page.getByLabel(/gênero/i).click()
      await page.getByRole('option', { name: /feminino/i }).click()

      // Select treatment type
      await page.getByLabel(/tipo de tratamento/i).click()
      await page.getByRole('option', { name: /quimioterapia/i }).click()

      // Submit form
      await page.getByRole('button', { name: /criar paciente/i }).click()

      // Should show success message
      await expect(page.getByText(/paciente criado com sucesso/i)).toBeVisible({ timeout: 10000 })

      // Dialog should close
      await expect(page.getByRole('dialog')).not.toBeVisible()

      // Should redirect to patient detail or show in list
      await expect(page.getByText('Maria da Silva')).toBeVisible({ timeout: 5000 })
    })

    test('should show validation errors for invalid data', async ({ page }) => {
      await page.getByRole('button', { name: /novo paciente/i }).click()

      // Try to submit empty form
      await page.getByRole('button', { name: /criar paciente/i }).click()

      // Should show validation errors
      await expect(page.getByText(/nome é obrigatório/i)).toBeVisible()
      await expect(page.getByText(/email é obrigatório/i)).toBeVisible()

      // Test invalid email
      await page.getByLabel(/email/i).fill('invalid-email')
      await page.getByRole('button', { name: /criar paciente/i }).click()

      await expect(page.getByText(/email inválido/i)).toBeVisible()

      // Test invalid phone
      await page.getByLabel(/telefone/i).fill('123')
      await page.getByRole('button', { name: /criar paciente/i }).click()

      await expect(page.getByText(/telefone inválido/i)).toBeVisible()
    })

    test('should handle server errors gracefully', async ({ page }) => {
      // Mock network failure
      await page.route('**/api/v2/patients', route => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ message: 'Internal server error' })
        })
      })

      await page.getByRole('button', { name: /novo paciente/i }).click()

      // Fill valid form data
      await page.getByLabel(/nome completo/i).fill('Test Patient')
      await page.getByLabel(/email/i).fill('test@example.com')
      await page.getByLabel(/telefone/i).fill('11999999999')

      await page.getByRole('button', { name: /criar paciente/i }).click()

      // Should show error message
      await expect(page.getByText(/erro ao criar paciente/i)).toBeVisible({ timeout: 10000 })
    })
  })

  test.describe('Patient Details', () => {
    test('should view patient details', async ({ page }) => {
      // Click on first patient (assuming patients exist)
      const firstPatient = page.getByTestId('patient-card').first()

      if (await firstPatient.isVisible()) {
        const patientName = await firstPatient.getByTestId('patient-name').textContent()

        await firstPatient.click()

        // Should navigate to patient detail page
        await expect(page).toHaveURL(/.*\/patients\/[^\/]+/)

        // Should show patient information
        if (patientName) {
          await expect(page.getByText(patientName)).toBeVisible()
        }

        // Should have patient tabs or sections
        await expect(page.getByRole('tab', { name: /informações/i }).or(
          page.getByText(/informações básicas/i)
        )).toBeVisible()
      }
    })

    test('should edit patient information', async ({ page }) => {
      // Navigate to first patient
      const firstPatient = page.getByTestId('patient-card').first()

      if (await firstPatient.isVisible()) {
        await firstPatient.click()

        // Look for edit button
        const editButton = page.getByRole('button', { name: /editar/i }).or(
          page.getByTestId('edit-patient-button')
        )

        if (await editButton.isVisible()) {
          await editButton.click()

          // Should open edit form/dialog
          await expect(page.getByText(/editar paciente/i).or(
            page.getByRole('dialog')
          )).toBeVisible()

          // Update name
          const nameField = page.getByLabel(/nome completo/i)
          await nameField.clear()
          await nameField.fill('Nome Atualizado')

          // Save changes
          await page.getByRole('button', { name: /salvar/i }).click()

          // Should show success message
          await expect(page.getByText(/paciente atualizado/i)).toBeVisible({ timeout: 10000 })

          // Should show updated name
          await expect(page.getByText('Nome Atualizado')).toBeVisible()
        }
      }
    })

    test('should change patient status', async ({ page }) => {
      const firstPatient = page.getByTestId('patient-card').first()

      if (await firstPatient.isVisible()) {
        await firstPatient.click()

        // Look for status change option
        const moreOptions = page.getByTestId('patient-actions').or(
          page.getByLabel(/mais opções/i)
        )

        if (await moreOptions.isVisible()) {
          await moreOptions.click()

          const statusOption = page.getByRole('menuitem', { name: /alterar status/i })

          if (await statusOption.isVisible()) {
            await statusOption.click()

            // Select new status
            await page.getByRole('option', { name: /pausado/i }).click()

            // Confirm change
            await page.getByRole('button', { name: /confirmar/i }).click()

            // Should show updated status
            await expect(page.getByText(/pausado/i)).toBeVisible({ timeout: 5000 })
          }
        }
      }
    })
  })

  test.describe('Patient Messages', () => {
    test('should send message to patient', async ({ page }) => {
      const firstPatient = page.getByTestId('patient-card').first()

      if (await firstPatient.isVisible()) {
        // Use message button from patient card
        const messageButton = firstPatient.getByTestId('message-button').or(
          firstPatient.getByRole('button', { name: /mensagem/i })
        )

        if (await messageButton.isVisible()) {
          await messageButton.click()

          // Should open message dialog
          await expect(page.getByRole('dialog')).toBeVisible()
          await expect(page.getByText(/enviar mensagem/i)).toBeVisible()

          // Type message
          const messageInput = page.getByLabel(/mensagem/i).or(
            page.getByPlaceholder(/digite sua mensagem/i)
          )

          await messageInput.fill('Olá! Como você está se sentindo hoje?')

          // Send message
          await page.getByRole('button', { name: /enviar/i }).click()

          // Should show success
          await expect(page.getByText(/mensagem enviada/i)).toBeVisible({ timeout: 10000 })

          // Dialog should close
          await expect(page.getByRole('dialog')).not.toBeVisible()
        }
      }
    })

    test('should view message history', async ({ page }) => {
      const firstPatient = page.getByTestId('patient-card').first()

      if (await firstPatient.isVisible()) {
        await firstPatient.click()

        // Look for messages tab
        const messagesTab = page.getByRole('tab', { name: /mensagens/i }).or(
          page.getByText(/histórico de mensagens/i)
        )

        if (await messagesTab.isVisible()) {
          await messagesTab.click()

          // Should show message list
          await expect(page.getByTestId('message-list').or(
            page.getByText(/mensagens/i)
          )).toBeVisible()

          // If messages exist, should show them
          const messages = page.getByTestId('message-item')
          const messageCount = await messages.count()

          if (messageCount > 0) {
            // Check message structure
            const firstMessage = messages.first()
            await expect(firstMessage.getByTestId('message-content')).toBeVisible()
            await expect(firstMessage.getByTestId('message-timestamp')).toBeVisible()
          } else {
            // Should show empty state
            await expect(page.getByText(/nenhuma mensagem/i)).toBeVisible()
          }
        }
      }
    })
  })

  test.describe('Accessibility', () => {
    test('should be keyboard navigable', async ({ page }) => {
      // Tab through main navigation elements
      await page.keyboard.press('Tab')
      await expect(page.getByRole('button', { name: /novo paciente/i })).toBeFocused()

      await page.keyboard.press('Tab')
      // Should focus on first patient or search input
      const focusedElement = page.locator(':focus')
      await expect(focusedElement).toBeVisible()
    })

    test('should have proper ARIA labels', async ({ page }) => {
      // Check main content area
      await expect(page.getByRole('main')).toBeVisible()

      // Check table has proper headers
      const table = page.getByTestId('patients-table')
      if (await table.isVisible()) {
        await expect(table.getByRole('columnheader')).toHaveCount.greaterThan(0)
      }

      // Check buttons have accessible names
      const createButton = page.getByRole('button', { name: /novo paciente/i })
      await expect(createButton).toBeVisible()
    })

    test('should work with screen reader announcements', async ({ page }) => {
      // Check for aria-live regions
      const liveRegions = page.locator('[aria-live]')
      const count = await liveRegions.count()

      // Should have at least one live region for status updates
      expect(count).toBeGreaterThan(0)

      // Check for proper headings hierarchy
      const headings = page.getByRole('heading')
      const h1Count = await page.getByRole('heading', { level: 1 }).count()
      expect(h1Count).toBeGreaterThanOrEqual(1)
    })
  })

  test.describe('Performance', () => {
    test('should load patient list quickly @performance', async ({ page }) => {
      const startTime = Date.now()

      await page.goto('/patients')

      // Wait for content to be visible
      await expect(page.getByTestId('patients-table')).toBeVisible()

      const loadTime = Date.now() - startTime

      // Should load within 3 seconds
      expect(loadTime).toBeLessThan(3000)
    })

    test('should handle large patient lists efficiently @performance', async ({ page }) => {
      // Navigate to patients page
      await page.goto('/patients')

      // Measure rendering performance
      const metrics = await page.evaluate(() => {
        const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
        return {
          domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
          loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
          firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0
        }
      })

      // Performance thresholds
      expect(metrics.domContentLoaded).toBeLessThan(1000) // 1 second
      expect(metrics.firstPaint).toBeLessThan(1500) // 1.5 seconds
    })
  })
})
