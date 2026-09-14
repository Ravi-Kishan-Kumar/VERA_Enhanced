import { expect, test } from "@playwright/test"

const product = {
  asin: "B0TEST1234",
  title: "Fixture earbuds",
  corrected_score: 4.2,
  uncertainty: 0.4,
  trust_weighted_score: 4.1,
  star_average: 4.5,
  review_count: 8,
  rank_position: 1,
  aspect_summary: null,
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) => route.fulfill({
    status: new URL(route.request().url()).pathname === "/api/ready" ? 200 : 501,
    contentType: "application/json",
    body: JSON.stringify({ status: "ready", database: true }),
  }))
})

test("analyzer, rankings, and methodology render honest real states", async ({ page }) => {
  await page.route("**/api/products?**", (route) => route.fulfill({ status: 200, headers: { "X-Total-Count": "0" }, contentType: "application/json", body: "[]" }))
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "See the experience behind the stars." })).toBeVisible()
  await expect(page.getByLabel("Review text")).toBeVisible()
  await expect(page.getByText("Round 1 · 1,059 labels")).toBeVisible()

  await page.goto("/products")
  await expect(page.getByRole("heading", { name: "Ranked by experience, not clicks." })).toBeVisible()
  await expect(page.getByRole("heading", { name: "No ranked products yet" })).toBeVisible()

  await page.goto("/about")
  await expect(page.getByRole("heading", { name: "How VERA reads a review." })).toBeVisible()
  await expect(page.getByText(/reference annotations used for agreement were produced by Claude, an LLM — not by humans/i)).toBeVisible()
  await expect(page.getByText("Round 1 · 1,059 labels")).toBeVisible()
})

test("all target viewports avoid horizontal page overflow", async ({ page }) => {
  for (const width of [360, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 800 })
    await page.goto("/")
    await expect(page.getByLabel("Review text")).toBeVisible()
    const dimensions = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, content: document.documentElement.scrollWidth }))
    expect(dimensions.content, `overflow at ${width}px`).toBeLessThanOrEqual(dimensions.viewport)
  }
})

test("rankings render returned rows and support mobile cards", async ({ page }) => {
  await page.route("**/api/products?**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([product]) }))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/products")
  await expect(page.getByRole("link", { name: /Fixture earbuds/ })).toBeVisible()
  await expect(page.getByText("1 products · page 1 of 1")).toBeVisible()
})

test("failed pagination preserves the product and loaded reviews", async ({ page }) => {
  const savedReviews = Array.from({ length: 20 }, (_, index) => ({
    id: index + 1, status: "done", text: `Saved review ${index + 1}: the sound is balanced and comfortable for everyday listening.`, star_rating: 4.5,
    helpful_votes: null, verified_purchase: null, product_title: "Fixture earbuds", product_asin: product.asin, corrected_score: 4.2,
    interval_lower: 3.8, interval_upper: 4.6, confidence_value: 0.7, star_text_gap: 0.3, review_quality: 0.9, aspects: null,
    flags: {}, explanation: null, error_message: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  }))
  await page.route("**/api/products/B0TEST1234?**", (route) => {
    if (new URL(route.request().url()).searchParams.get("reviews_offset") === "20") return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Unavailable" }) })
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...product, review_count: 21, eb_shrinkage_factor: 0.5, last_aggregated_at: "2026-01-01T00:00:00Z", reviews: savedReviews, reviews_total: 21, reviews_limit: 20, reviews_offset: 0, reviews_has_more: true }) })
  })
  await page.goto("/products/B0TEST1234")
  await page.getByRole("button", { name: "Show more reviews" }).click()
  await expect(page.getByRole("alert").filter({ hasText: "temporarily unavailable" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Fixture earbuds" })).toBeVisible()
  await expect(page.getByText(/Saved review 1:/)).toBeVisible()
  await expect(page.getByText("20 / 21")).toBeVisible()
})

test("rate limiting preserves input and honors Retry-After without auto-submit", async ({ page }) => {
  let submissions = 0
  await page.route("**/api/reviews", (route) => { submissions += 1; return route.fulfill({ status: 429, headers: { "Retry-After": "2", "X-Request-ID": "test-rate-limit" }, contentType: "application/json", body: JSON.stringify({ detail: "unsafe internal detail" }) }) })
  await page.goto("/")
  await page.getByRole("button", { name: "Mixed reliability" }).click()
  const draft = await page.getByLabel("Review text").inputValue()
  await page.getByRole("button", { name: "Analyze review" }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Too many requests")
  await expect(page.getByRole("button", { name: /Try again in/ })).toBeDisabled()
  await expect(page.getByLabel("Review text")).toHaveValue(draft)
  await expect(page.getByRole("button", { name: "Analyze review" })).toBeEnabled({ timeout: 5_000 })
  expect(submissions).toBe(1)
})

test("unavailable readiness preserves a draft and recovers only on retry", async ({ page }) => {
  let available = false
  let submissions = 0
  await page.route("**/api/ready", (route) => route.fulfill({ status: available ? 200 : 503, contentType: "application/json", body: JSON.stringify({ status: available ? "ready" : "unavailable", database: available }) }))
  await page.route("**/api/reviews", (route) => { submissions += 1; return route.abort() })
  await page.goto("/")
  await page.getByRole("button", { name: "Detailed praise" }).click()
  const draft = await page.getByLabel("Review text").inputValue()
  await expect(page.getByRole("complementary", { name: "Service availability" })).toContainText("temporarily unavailable")
  await page.getByRole("button", { name: "Analyze review" }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("temporarily unavailable")
  expect(submissions).toBe(0)
  await expect(page.getByLabel("Review text")).toHaveValue(draft)
  available = true
  await page.getByRole("button", { name: "Retry connection" }).click()
  await expect(page.getByRole("complementary", { name: "Service availability" })).toHaveCount(0)
  await expect(page.getByLabel("Review text")).toHaveValue(draft)
})

test("keyboard navigation, reduced motion, theme, command, and metadata work", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "light" })
  await page.goto("/")
  await page.keyboard.press("Tab")
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused()
  await page.keyboard.press("Enter")
  await expect(page.locator("main")).toBeFocused()
  const animationDuration = await page.locator("main > div").evaluate((element) => Number.parseFloat(getComputedStyle(element).animationDuration))
  expect(animationDuration).toBeLessThanOrEqual(0.01)
  const rating = page.getByRole("slider", { name: /Original star rating/ })
  await rating.focus(); await page.keyboard.press("ArrowRight"); await expect(rating).toHaveValue("4.5")
  await page.keyboard.press("Control+k"); await expect(page.getByRole("dialog", { name: "Navigate VERA" })).toBeVisible(); await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "Switch to dark theme" }).click(); await expect(page.locator("html")).toHaveClass(/dark/)
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute("content", "See the experience behind the stars")
  await page.goto("/about")
  await expect(page.locator('a[href="/about"][aria-current="page"]').first()).toHaveAttribute("aria-current", "page")
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1)
  await expect(page).toHaveTitle("Methodology | VERA")
})

test("completed analysis focuses its result and exposes chart alternatives", async ({ page }) => {
  await page.route("**/api/reviews", (route) => route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ review_id: 42, task_id: "test", status: "pending", message: "queued" }) }))
  await page.route("**/api/reviews/42", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
    id: 42, status: "done", text: "Fixture review text", star_rating: 5, helpful_votes: null, verified_purchase: null, product_title: null, product_asin: null,
    corrected_score: 3.2, interval_lower: 2.8, interval_upper: 3.6, confidence_value: 0.8, star_text_gap: 1.8, review_quality: 0.7,
    aspects: null, flags: {}, explanation: "Mixed listening experience in this test fixture.", error_message: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  }) }))
  await page.goto("/")
  await page.getByRole("button", { name: "Mixed reliability" }).click()
  await page.getByRole("button", { name: "Analyze review" }).click()
  await expect(page.getByTestId("score-result")).toBeVisible()
  await expect(page.getByTestId("analysis-output")).toBeFocused()
  await expect(page.getByText("Mixed listening experience in this test fixture.")).toBeVisible()
  await expect(page.getByRole("tab", { name: "Bars" })).toBeVisible()
  await expect(page.getByLabel("Aspect sentiment values")).toBeVisible()
})

test("light and dark screenshots remain stable", async ({ page }, testInfo) => {
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "See the experience behind the stars." })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("home-light.png"), fullPage: true, animations: "disabled" })
  await page.getByRole("button", { name: "Switch to dark theme" }).click()
  await page.screenshot({ path: testInfo.outputPath("home-dark.png"), fullPage: true, animations: "disabled" })
})
