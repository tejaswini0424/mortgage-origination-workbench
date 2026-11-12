import { expect, test } from "@playwright/test";
import { execFileSync, spawn } from "node:child_process";
import { resolve } from "node:path";
import { catalog } from "../src/catalog";

test("processor workspace reviews evidence and exports a packet", async ({
  page,
}) => {
  const root = resolve(process.cwd(), "..");
  execFileSync("python", ["-m", "benchmarks.samples"], { cwd: root });
  const worker = spawn("python", ["-m", "backend.app.worker"], {
    cwd: root,
    env: { ...process.env, MORTGAGE_DATA: process.env.WORKBENCH_BROWSER_DATA },
    stdio: "ignore",
  });
  try {
    await page.goto("/");
    await page.getByLabel("Username").fill("reviewer");
    await page.getByLabel("Password").fill("browser-test-local");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(
      page.getByRole("heading", { name: "Portfolio overview" }),
    ).toBeVisible();
    await page
      .getByRole("main")
      .getByRole("link", { name: "New case" })
      .click();
    await page.getByLabel("Case title").fill("Browser workflow " + Date.now());
    await page.getByLabel("Borrower name").fill("Fictional Borrower 10000");
    await page.getByRole("button", { name: "Create case" }).click();
    await page
      .getByLabel("Upload PDF, PNG, or JPEG")
      .setInputFiles(resolve(root, "runtime/samples/pay_stub.pdf"));
    await page.getByRole("button", { name: "Upload document" }).click();
    await expect(
      page.getByText("Employee Name: Fictional Borrower 10000"),
    ).toBeVisible({ timeout: 15000 });
    await expect(
      page.getByRole("img", { name: "Document page 1" }),
    ).toBeVisible();
    const confirms = page.getByRole("button", { name: "Confirm or correct" });
    while (await confirms.count()) {
      const count = await confirms.count();
      await confirms.first().click();
      await expect(confirms).toHaveCount(count - 1);
    }
    page.once("dialog", (dialog) =>
      dialog.accept(
        "Synthetic demonstration. Other checklist items are missing.",
      ),
    );
    await page.getByRole("button", { name: "Release reviewed case" }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download reviewed packet" }).click();
    expect((await download).suggestedFilename()).toMatch(/^case-.*\.json$/);
  } finally {
    worker.kill();
  }
});

test("all 32 catalog destinations open directly and through navigation", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("reviewer");
  await page.getByLabel("Password").fill("browser-test-local");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Portfolio overview" }),
  ).toBeVisible();
  const items = catalog.flatMap((group) => group.items);
  expect(items).toHaveLength(32);
  const headings: Record<string, string> = {
    "/": "Portfolio overview",
    "/cases": "Mortgage cases",
    "/new": "New mortgage case",
  };
  for (const [path, label] of items) {
    await page
      .locator("aside")
      .getByRole("link", { name: label, exact: true })
      .click();
    await expect(page).toHaveURL(new RegExp(path.replace("/", "\\/") + "$"));
    await expect(
      page.getByRole("heading", { name: headings[path] ?? label, level: 1 }),
    ).toBeVisible();
  }
  await page.goto("/tools/income");
  await expect(
    page.getByRole("heading", { name: "Income worksheet", level: 1 }),
  ).toBeVisible();
});

test("a queued research run persists and appears in comparison and robustness views", async ({
  page,
}) => {
  test.setTimeout(120000);
  const root = resolve(process.cwd(), "..");
  const worker = spawn("python", ["-m", "backend.app.worker"], {
    cwd: root,
    env: { ...process.env, MORTGAGE_DATA: process.env.WORKBENCH_BROWSER_DATA },
    stdio: "ignore",
  });
  try {
    await page.goto("/research");
    await page.getByLabel("Username").fill("reviewer");
    await page.getByLabel("Password").fill("browser-test-local");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.getByRole("button", { name: "Run evaluation" }).click();
    await expect(
      page.getByRole("heading", { name: "Results by condition" }),
    ).toBeVisible({ timeout: 95000 });
    await expect(
      page.getByRole("link", { name: "Download report" }),
    ).toBeVisible();
    await page
      .locator("aside")
      .getByRole("link", { name: "Model comparison" })
      .click();
    await expect(
      page.getByRole("heading", { name: "Aggregate performance" }),
    ).toBeVisible();
    await expect(
      page.getByRole("cell", { name: "layout_verified", exact: true }),
    ).toBeVisible();
    await page
      .locator("aside")
      .getByRole("link", { name: "Robustness analysis" })
      .click();
    await expect(
      page.getByRole("heading", { name: "Results by condition" }),
    ).toBeVisible();
    await expect(page.getByRole("cell", { name: "rotated scan" })).toHaveCount(
      3,
    );
  } finally {
    worker.kill();
  }
});
