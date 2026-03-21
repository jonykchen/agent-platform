// tests/e2e/login.spec.ts
import { test, expect } from '@playwright/test';

const TEST_USERS = {
  admin: { username: 'admin', password: 'admin123' },
  operator: { username: 'operator', password: 'operator123' },
  viewer: { username: 'viewer', password: 'viewer123' },
};

test.describe('Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('should display login page', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Agent Platform');
    await expect(page.locator('[name="username"]')).toBeVisible();
    await expect(page.locator('[name="password"]')).toBeVisible();
  });

  test('should login successfully with admin credentials', async ({ page }) => {
    await page.fill('[name="username"]', TEST_USERS.admin.username);
    await page.fill('[name="password"]', TEST_USERS.admin.password);
    await page.click('button[type="submit"]');

    // Should redirect to chat page
    await expect(page).toHaveURL(/\/chat/, { timeout: 10000 });
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.fill('[name="username"]', 'invalid');
    await page.fill('[name="password"]', 'invalid');
    await page.click('button[type="submit"]');

    // Should show error message
    await expect(page.locator('.ant-alert-error')).toBeVisible({ timeout: 5000 });
  });

  test('should redirect to requested page after login', async ({ page }) => {
    // Try to access protected page
    await page.goto('/approval');

    // Should redirect to login with redirect param
    await expect(page).toHaveURL(/\/login/);

    // Login
    await page.fill('[name="username"]', TEST_USERS.admin.username);
    await page.fill('[name="password"]', TEST_USERS.admin.password);
    await page.click('button[type="submit"]');

    // Should redirect back to approval
    await expect(page).toHaveURL(/\/approval/, { timeout: 10000 });
  });
});

// tests/e2e/navigation.spec.ts
test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="username"]', TEST_USERS.admin.username);
    await page.fill('[name="password"]', TEST_USERS.admin.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/chat/);
  });

  test('should navigate via sidebar', async ({ page }) => {
    // Click approval in sidebar
    await page.click('[data-testid="sidebar-item-approval"]');
    await expect(page).toHaveURL(/\/approval/);

    // Click tools in sidebar
    await page.click('[data-testid="sidebar-item-tools"]');
    await expect(page).toHaveURL(/\/tools/);
  });

  test('should show user dropdown', async ({ page }) => {
    await page.click('.ant-avatar');
    await expect(page.locator('.ant-dropdown-menu')).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    await page.click('.ant-avatar');
    await page.click('text=退出登录');

    await expect(page).toHaveURL(/\/login/);
  });
});

// tests/e2e/permissions.spec.ts
test.describe('Permission Boundaries', () => {
  test('viewer cannot access tool management', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="username"]', TEST_USERS.viewer.username);
    await page.fill('[name="password"]', TEST_USERS.viewer.password);
    await page.click('button[type="submit"]');

    // Sidebar should not show tools item
    await expect(page.locator('[data-testid="sidebar-item-tools"]')).not.toBeVisible();
  });

  test('operator can approve requests', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name="username"]', TEST_USERS.operator.username);
    await page.fill('[name="password"]', TEST_USERS.operator.password);
    await page.click('button[type="submit"]');

    await page.goto('/approval');

    // Should see approve button
    await expect(page.locator('[data-testid="approve-button"]')).toBeVisible();
  });
});