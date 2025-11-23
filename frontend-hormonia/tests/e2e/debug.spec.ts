import { test, expect } from '@playwright/test';

test('Debug Login Page', async ({ page }) => {
    console.log('Navigating to login...');
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err));

    try {
        await page.goto('/login', { timeout: 10000 });
        console.log('Page loaded.');
        console.log('Page title:', await page.title());

        const content = await page.content();
        console.log('Page content length:', content.length);

        await expect(page.locator('#root')).toBeVisible({ timeout: 5000 });
        console.log('Root element visible');

        await expect(page.locator('form')).toBeVisible({ timeout: 5000 });
        console.log('Form visible');

    } catch (e) {
        console.log('Test failed:', e);
        // Take screenshot
        await page.screenshot({ path: 'debug-screenshot.png' });
        throw e;
    }
});
