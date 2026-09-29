import { expect, test } from "@playwright/test";

test("landing demo collector lot then admin approval", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("tour-collector", "1");
    localStorage.setItem("tour-admin", "1");
    localStorage.setItem("kabadi_lang", "en");
  });
  await page.goto("/");
  await page.getByTestId("try-demo").click();
  await page.getByTestId("demo-collector").click();
  await expect(page).toHaveURL(/\/app\/collector/, { timeout: 15000 });
  await expect(page.getByTestId("collector-earnings")).toBeVisible();
  await page.getByTestId("nav-lots").click();
  await page.getByTestId("create-lot").click();
  await expect(page.getByText(/LOT-/)).toBeVisible({ timeout: 20000 });
  await page.getByTestId("logout").click();
  await page.getByTestId("demo-admin").click();
  await expect(page).toHaveURL(/\/app\/admin/, { timeout: 15000 });
  await page.getByTestId("nav-verification").click();
  await page.getByTestId("approve-recycler").first().click();
  await expect(page.getByText("approved")).toBeVisible();
});
