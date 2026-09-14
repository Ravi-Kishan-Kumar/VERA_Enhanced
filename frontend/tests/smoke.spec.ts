import { expect, test } from "@playwright/test";

// Never contact the shared API/worker during UI tests; individual tests override fixtures.
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) => route.fulfill({
    status: new URL(route.request().url()).pathname === "/api/ready" ? 200 : 501,
    contentType: "application/json",
    body: JSON.stringify({ status: "ready", database: true }),
  }));
});

test("analyzer, rankings, and methodology routes render their real states", async ({ page }) => {
  await page.route("**/api/products?**", (route) =>
    route.fulfill({ status: 200, headers: { "X-Total-Count": "0" }, contentType: "application/json", body: "[]" }),
  );

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Go beyond the stars." })).toBeVisible();
  await expect(page.getByLabel("Review text")).toBeVisible();

  await page.goto("/products");
  await expect(page.getByRole("heading", { name: "Ranked by experience, not clicks." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No ranked products yet" })).toBeVisible();

  await page.goto("/about");
  await expect(page.getByRole("heading", { name: "How VERA reads a review." })).toBeVisible();
  await expect(page.getByText(/reference annotations used for agreement are from Claude, not human reviewers/i)).toBeVisible();
});

test("the analyzer fits a narrow mobile viewport without horizontal page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/");
  await expect(page.getByLabel("Review text")).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
});

test("rankings fall back to the returned row count when the total header is absent", async ({ page }) => {
  await page.route("**/api/products?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{
        asin: "B0TEST1234",
        title: "Fixture earbuds",
        corrected_score: 4.2,
        uncertainty: 0.4,
        trust_weighted_score: 4.1,
        star_average: 4.5,
        review_count: 8,
        rank_position: 1,
        aspect_summary: null,
      }]),
    }),
  );

  await page.goto("/products");
  await expect(page.getByRole("link", { name: /Fixture earbuds/ })).toBeVisible();
  await expect(page.getByText("Page 1 / 1 · 1 products")).toBeVisible();
});

test("a failed next-page request preserves the product and reviews already loaded", async ({ page }) => {
  const savedReviews = Array.from({ length: 20 }, (_, index) => ({
    id: index + 1,
    status: "done",
    text: `Saved review ${index + 1}: the sound is balanced and comfortable for everyday listening.`,
    star_rating: 4.5,
    helpful_votes: null,
    verified_purchase: null,
    product_title: "Fixture earbuds",
    product_asin: "B0TEST1234",
    corrected_score: 4.2,
    interval_lower: 3.8,
    interval_upper: 4.6,
    confidence_value: 0.7,
    star_text_gap: 0.3,
    review_quality: 0.9,
    aspects: null,
    flags: {},
    explanation: null,
    error_message: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  }));

  await page.route("**/api/products/B0TEST1234?**", (route) => {
    const offset = new URL(route.request().url()).searchParams.get("reviews_offset");
    if (offset === "20") {
      return route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "The aggregate store is temporarily unavailable." }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        asin: "B0TEST1234",
        title: "Fixture earbuds",
        corrected_score: 4.2,
        uncertainty: 0.4,
        trust_weighted_score: 4.1,
        star_average: 4.5,
        review_count: 21,
        rank_position: 1,
        aspect_summary: null,
        eb_shrinkage_factor: 0.5,
        last_aggregated_at: "2026-01-01T00:00:00Z",
        reviews: savedReviews,
        reviews_total: 21,
        reviews_limit: 20,
        reviews_offset: 0,
        reviews_has_more: true,
      }),
    });
  });

  await page.goto("/products/B0TEST1234");
  await expect(page.getByRole("heading", { name: "Fixture earbuds" })).toBeVisible();
  await page.getByRole("button", { name: "Load more reviews" }).click();
  await expect(page.locator(".load-more-error")).toContainText("temporarily unavailable");
  await expect(page.getByRole("heading", { name: "Fixture earbuds" })).toBeVisible();
  await expect(page.getByText(/Saved review 1:/)).toBeVisible();
  await expect(page.getByText("20 / 21")).toBeVisible();
});

test("rate limiting preserves input and waits for Retry-After without auto-resubmitting", async ({ page }) => {
  let submissions = 0;
  await page.route("**/api/reviews", (route) => {
    submissions += 1;
    return route.fulfill({ status: 429, headers: { "Retry-After": "2", "X-Request-ID": "test-rate-limit" }, contentType: "application/json", body: JSON.stringify({ detail: "internal detail must not replace safe copy" }) });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Mixed experience" }).click();
  const text = await page.getByLabel("Review text").inputValue();
  await page.getByRole("button", { name: "Analyze experience" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Too many requests");
  await expect(page.getByRole("button", { name: /Try again in/ })).toBeDisabled();
  await expect(page.getByLabel("Review text")).toHaveValue(text);
  await expect(page.getByRole("button", { name: "Analyze experience" })).toBeEnabled({ timeout: 5000 });
  expect(submissions).toBe(1);
});

test("unavailable readiness preserves a draft and recovers through an explicit retry", async ({ page }) => {
  let available = false;
  let submissions = 0;
  await page.route("**/api/ready", (route) => route.fulfill({ status: available ? 200 : 503, contentType: "application/json", body: JSON.stringify({ status: available ? "ready" : "unavailable", database: available }) }));
  await page.route("**/api/reviews", (route) => { submissions += 1; return route.abort(); });
  await page.goto("/");
  await page.getByRole("button", { name: "Positive detail" }).click();
  const draft = await page.getByLabel("Review text").inputValue();
  await expect(page.getByRole("complementary", { name: "Service availability" })).toContainText("temporarily unavailable");
  await page.getByRole("button", { name: "Analyze experience" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("temporarily unavailable");
  expect(submissions).toBe(0);
  await expect(page.getByLabel("Review text")).toHaveValue(draft);
  available = true;
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(page.getByRole("complementary", { name: "Service availability" })).toHaveCount(0);
  await expect(page.getByLabel("Review text")).toHaveValue(draft);
});

test("keyboard navigation, reduced motion, and metadata work without a backend", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  expect(await page.locator(".page-enter").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", "Beyond the star rating");
  await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute("content", "summary_large_image");
  await page.getByRole("navigation").getByRole("link", { name: "Methodology" }).click();
  await expect(page.getByRole("navigation").getByRole("link", { name: "Methodology" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page).toHaveTitle("Methodology | VERA");
  const robots = await page.request.get("/robots.txt");
  expect(await robots.text()).toContain("Disallow: /api/");
  const sitemap = await page.request.get("/sitemap.xml");
  expect(await sitemap.text()).toContain("/products</loc>");
});

test("completed analysis focuses its result and keeps chart alternatives readable", async ({ page }) => {
  await page.route("**/api/reviews", (route) => route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ review_id: 42, status: "pending" }) }));
  await page.route("**/api/reviews/42", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
    id: 42, status: "done", star_rating: 5, corrected_score: 3.2, interval_lower: 2.8, interval_upper: 3.6,
    confidence_value: 0.8, star_text_gap: 1.8, review_quality: 0.7, aspects: null, flags: {},
    explanation: "Mixed listening experience in this test fixture.", product_asin: null,
  }) }));
  await page.goto("/");
  await page.getByRole("button", { name: "Mixed experience" }).click();
  await page.getByRole("button", { name: "Analyze experience" }).click();
  await expect(page.locator(".score-card")).toBeVisible();
  await expect(page.locator(".analysis-output")).toBeFocused();
  await expect(page.getByText("Mixed listening experience in this test fixture.")).toBeVisible();
});

test("home visual snapshot", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Go beyond the stars." })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Service availability" })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("home.png"), fullPage: true, animations: "disabled" });
});
