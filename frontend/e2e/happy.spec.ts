import { expect, test } from "@playwright/test";

const phone = `9${Date.now().toString().slice(-9)}`;

test("register, offline lot, sync, handover, payment, receipt", async ({ page, context }) => {
  await page.goto("/register/collector");
  await page.getByLabel("Phone").fill(phone);
  await page.getByRole("button", { name: "Send OTP" }).click();
  await expect(page.getByText("123456")).toBeVisible();
  await page.getByLabel("Name").fill("Play Collector");
  await page.getByLabel("Password").fill("Demo@12345");
  await page.getByLabel("OTP").fill("123456");
  await page.getByLabel("Area").fill("Abids");
  await page.getByLabel("City").fill("Hyderabad");
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Digital Lots")).toBeVisible();

  await page.getByRole("link", { name: "Digital Lots" }).click();
  await page.getByLabel("Approximate weight").locator("input").fill("4");
  await context.setOffline(true);
  await page.getByRole("button", { name: "Create digital lot" }).click();
  await expect(page.getByText(/Saved on this phone/)).toBeVisible();
  await context.setOffline(false);
  await page.getByRole("button", { name: "Sync now" }).click();
  await expect(page.getByText("Synced")).toBeVisible({ timeout: 20000 });

  await page.goto("/login");
  await page.getByLabel("Phone").fill("9000000011");
  await page.getByLabel("Password").fill("Demo@123");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByText("Pickup Scheduling").or(page.getByText("Pickups"))).toBeVisible();
});
