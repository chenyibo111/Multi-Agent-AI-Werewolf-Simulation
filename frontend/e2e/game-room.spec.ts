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

test("a room can be resumed from local history and deleted", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("选择身份").selectOption("seer");
  await page.getByRole("button", { name: "开始对局" }).click();
  await expect(page.getByText("预言家查验")).toBeVisible();

  await page.getByRole("link", { name: "Werewolf Arena" }).click();
  await expect(page.getByRole("heading", { name: "继续对局" })).toBeVisible();
  await expect(page.getByText("进行中的对局")).toBeVisible();

  await page.getByRole("button", { name: "继续对局" }).click();
  await expect(page.getByText("预言家查验")).toBeVisible();

  await page.getByRole("link", { name: "Werewolf Arena" }).click();
  page.on("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "删除对局" }).click();
  await expect(page.getByText("暂无本地对局记录")).toBeVisible();
});

test("the human action panel stays docked beside a long desktop timeline", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/");
  await page.getByLabel("选择身份").selectOption("seer");
  await page.getByRole("button", { name: "开始对局" }).click();

  await expect(page.locator(".action-panel")).toHaveCSS("position", "sticky");
});

test("the room uses independent desktop scrolling panes instead of document scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/");
  await page.getByLabel("选择身份").selectOption("seer");
  await page.getByRole("button", { name: "开始对局" }).click();

  await expect(page.locator(".game-layout")).toHaveCSS("overflow-y", "hidden");
  await expect(page.locator(".timeline")).toHaveCSS("overflow-y", "auto");
  await expect(page.locator(".room-sidebar")).toHaveCSS("overflow-y", "auto");
});
