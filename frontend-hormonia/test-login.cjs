const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({
    headless: false,
    executablePath: '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
    args: ['--no-sandbox']
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('Navigating to login page...');
  await page.goto('http://localhost:5173');

  // Wait for page to load
  await page.waitForLoadState('networkidle');

  console.log('Page loaded. Taking screenshot...');
  await page.screenshot({ path: 'login-page.png' });

  // Look for email input
  const emailInput = await page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first();

  if (await emailInput.isVisible()) {
    console.log('Found email input, filling...');
    await emailInput.fill('admin@neoplasiaslitoral.com');
    await page.screenshot({ path: 'email-filled.png' });
    console.log('Email filled!');
  } else {
    console.log('Email input not found, checking page structure...');
    const pageContent = await page.content();
    console.log('Page title:', await page.title());
  }

  // Keep browser open for manual inspection
  console.log('Browser will stay open for 60 seconds...');
  await page.waitForTimeout(60000);

  await browser.close();
})();
