import { expect, test } from "@playwright/test";

test("a human seer can create, inspect, and see no private AI fields", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("选择身份").selectOption("seer");
  await page.getByRole("button", { name: "开始对局" }).click();
  await expect(page.getByText("预言家查验")).toBeVisible();
  await page.getByRole("button", { name: /AI 玩家/ }).first().click();
  await page.getByRole("button", { name: "确认查验" }).click();
  await expect(page.locator("body")).not.toContainText("agent_memory");
});
