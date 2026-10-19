import { test, expect } from "@playwright/test";

test("real ingested AWQ experiment comparison and PDF citation", async ({
  page,
}) => {
  test.skip(
    !process.env.PM_QA_TOKEN || !process.env.PM_QA_LIBRARY,
    "Optional existing real-paper smoke library",
  );
  await page.addInitScript(
    (token) => sessionStorage.setItem("papermind_token", token),
    process.env.PM_QA_TOKEN!,
  );
  await page.goto("/");
  await page.getByLabel("当前知识库").selectOption(process.env.PM_QA_LIBRARY!);
  await page.getByRole("button", { name: "实验探索", exact: true }).click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/real-experiments.png",
    fullPage: true,
  });
  await page.locator('tbody input[type="checkbox"]').nth(0).check();
  await page.locator('tbody input[type="checkbox"]').nth(1).check();
  await page.getByRole("button", { name: /比较所选/ }).click();
  await expect(
    page.getByText("INSUFFICIENT_INFORMATION", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/real-comparison.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "返回实验探索" }).click();
  await page
    .getByRole("button", { name: "检查", exact: false })
    .first()
    .click();
  await expect(page.getByLabel("已核对条件字段")).toBeVisible();
  await page.getByRole("button", { name: "查看原始证据" }).first().click();
  await expect(
    page.getByRole("heading", { name: "原始论文证据" }),
  ).toBeVisible();
  await expect(page.getByLabel("PDF 页码")).toHaveValue("4");
  const canvas = page.getByLabel("论文原文第 4 页");
  await expect(canvas).toHaveAttribute("data-rendered", "true", {
    timeout: 20000,
  });
  expect(
    await canvas.evaluate((element) => {
      const target = element as HTMLCanvasElement;
      const pixels = target
        .getContext("2d")!
        .getImageData(0, 0, target.width, target.height).data;
      let dark = 0;
      for (let n = 0; n < pixels.length; n += 16) {
        if (
          pixels[n] < 100 &&
          pixels[n + 1] < 100 &&
          pixels[n + 2] < 100 &&
          pixels[n + 3] > 0
        )
          dark++;
      }
      return dark;
    }),
  ).toBeGreaterThan(100);
  await page.screenshot({
    path: "../docs/screenshots/real-evidence.png",
    fullPage: true,
  });
});
