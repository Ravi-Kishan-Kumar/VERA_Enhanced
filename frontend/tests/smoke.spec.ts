import { expect, test } from "@playwright/test";

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
