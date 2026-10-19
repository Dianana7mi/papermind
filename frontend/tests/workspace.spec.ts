import { test, expect } from "@playwright/test";

test("real API: registration, library, every core screen, mobile and signout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/login.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "还没有账户？注册" }).click();
  await page.getByLabel("邮箱").fill(`browser-${Date.now()}@example.org`);
  await page.getByLabel("密码").fill("browser-test-password-123");
  await page.getByRole("button", { name: "创建账户", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Workspace overview" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "创建知识库", exact: true }).click();
  await page.getByLabel("知识库名称").fill("Browser QA · private library");
  await page
    .locator("form.modal")
    .getByRole("button", { name: "创建知识库", exact: true })
    .click();
  await expect(page.getByLabel("当前知识库")).toHaveValue(/.{36}/);
  await page.screenshot({
    path: "../docs/screenshots/dashboard.png",
    fullPage: true,
  });
  for (const [label, heading] of [
    ["论文库", "Paper library"],
    ["研究对话", "Research chat"],
    ["实验探索", "Experiment explorer"],
    ["实验比较", "Experiment comparison"],
    ["研究报告", "Research reports"],
    ["评测", "Evaluation lab"],
    ["设置", "Workspace settings"],
  ]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
  }
  await page.getByRole("button", { name: "研究对话", exact: true }).click();
  await page.getByLabel("检索模式").selectOption("bm25");
  await page
    .getByLabel("研究问题", { exact: true })
    .fill("What evidence exists in this empty library?");
  await page.getByRole("button", { name: "发送研究问题" }).click();
  await expect(
    page.getByText(
      "当前证据不足以生成已核验的回答。以下为检索到的原文片段，可打开论文核查：",
      { exact: true },
    ),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/research.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../docs/screenshots/mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "退出账户" }).click();
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  await page.getByRole("button", { name: "还没有账户？注册" }).click();
  await page
    .getByLabel("邮箱")
    .fill(`second-browser-${Date.now()}@example.org`);
  await page.getByLabel("密码").fill("second-test-password-123");
  await page.getByRole("button", { name: "创建账户", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Workspace overview" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "研究对话", exact: true }).click();
  await expect(
    page.getByText("What evidence exists in this empty library?", {
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(page.getByLabel("当前知识库")).toHaveValue("");
  expect(errors).toEqual([]);
});
