const { chromium } = require('playwright');

(async () => {
  console.log('Starting Playwright login test...');

  const browser = await chromium.launch({
    headless: false,
    executablePath: '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox']
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('Navigating to login page...');
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle', { timeout: 30000 });

    console.log('Page loaded. Taking screenshot...');
    await page.screenshot({ path: 'login-page-before.png' });

    // Wait for the page to fully render
    await page.waitForTimeout(2000);

    // Find email input
    console.log('Looking for email input...');
    const emailInput = await page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="Email" i]').first();

    if (await emailInput.isVisible({ timeout: 5000 })) {
      console.log('Found email input, filling...');
      await emailInput.fill('admin@neoplasiaslitoral.com');
      await page.screenshot({ path: 'email-filled.png' });

      // Find password input
      const passwordInput = await page.locator('input[type="password"]').first();
      if (await passwordInput.isVisible({ timeout: 3000 })) {
        console.log('Found password input, filling...');
        await passwordInput.fill('Admin@123456!');
        await page.screenshot({ path: 'password-filled.png' });

        // Find and click login button
        const loginButton = await page.locator('button[type="submit"], button:has-text("Entrar"), button:has-text("Login")').first();
        if (await loginButton.isVisible({ timeout: 3000 })) {
          console.log('Clicking login button...');
          await loginButton.click();

          // Wait for response
          await page.waitForLoadState('networkidle', { timeout: 30000 });
          await page.waitForTimeout(3000);
          await page.screenshot({ path: 'after-login.png' });

          // Check if login was successful
          const url = page.url();
          console.log('Current URL after login:', url);

          if (url.includes('dashboard') || url.includes('admin') || !url.includes('login')) {
            console.log('LOGIN SUCCESSFUL!');
          } else {
            console.log('Login may have failed - still on login page');

            // Check for error messages
            const errorText = await page.locator('.error, [role="alert"], .toast-error').textContent().catch(() => null);
            if (errorText) {
              console.log('Error message:', errorText);
            }
          }
        } else {
          console.log('Login button not found');
        }
      } else {
        console.log('Password input not found');
      }
    } else {
      console.log('Email input not found. Page structure:');
      const html = await page.content();
      console.log('Looking for inputs in page...');
      const inputs = await page.locator('input').all();
      console.log('Found', inputs.length, 'input elements');
      for (const input of inputs.slice(0, 5)) {
        console.log('- Input:', await input.getAttribute('type'), await input.getAttribute('name'), await input.getAttribute('placeholder'));
      }
    }

    console.log('Test completed. Browser will stay open for 30 seconds...');
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error('Error during test:', error.message);
    await page.screenshot({ path: 'error.png' });
  } finally {
    await browser.close();
  }
})();
