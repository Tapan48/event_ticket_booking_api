import { test, expect, type Page } from "@playwright/test";

const stamp = Date.now();
const organizer = `organizer-${stamp}@example.com`;
const attendee = `attendee-${stamp}@example.com`;
const password = "Frontend-demo-test-482!";
const title = `Browser Experience ${stamp}`;
const venue = `Browser Hall ${stamp}`;
async function signup(page: Page, email: string, role: string) {
  await page.goto("/register");
  await page
    .getByLabel("First name")
    .fill(role === "organizer" ? "Morgan" : "Alex");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("I’m here to").selectOption(role);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("link", {
      name: role === "organizer" ? "Morgan" : "Alex",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page).not.toHaveURL(/\/register/);
}
async function logout(page: Page) {
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "Sign in", exact: true }),
  ).toBeVisible();
}
async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

test("organizer creates and publishes; attendee books, pays, cancels; organizer checks in", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await signup(page, organizer, "organizer");
  await page.getByRole("link", { name: "My venues", exact: true }).click();
  await page.getByRole("button", { name: "Add venue", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("name", { exact: true }).fill(venue);
  await dialog.getByLabel("address", { exact: true }).fill("42 Test Street");
  await dialog.getByLabel("city", { exact: true }).fill("Pune");
  await dialog.getByRole("button", { name: "Save venue" }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("link", { name: "My events", exact: true }).click();
  await page.getByRole("link", { name: "Create event", exact: true }).click();
  await page.getByLabel("Event title").fill(title);
  await page
    .getByLabel("Description", { exact: true })
    .fill("A real browser-to-database verification event.");
  await page
    .getByRole("combobox", { name: "Venue", exact: true })
    .selectOption({ label: `${venue} · Pune` });
  await page.getByLabel("Starts at (your local time)").fill("2027-10-10T18:00");
  await page.getByLabel("Ends at (your local time)").fill("2027-10-10T21:00");
  await page.getByRole("button", { name: "Create event", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Ticket tiers", exact: true }),
  ).toBeVisible();
  const eventPath = page.url().match(/\/organizer(\/events\/\d+)/)![1];
  await page.getByRole("button", { name: "Add tier" }).click();
  await dialog.getByLabel("Tier name").fill("General");
  await dialog.getByLabel("Price (INR)").fill("10.00");
  await dialog.getByLabel("Total tickets").fill("5");
  await dialog.getByRole("button", { name: "Save tier" }).click();
  await expect(dialog).not.toBeVisible();
  await page
    .getByRole("combobox", { name: "Status", exact: true })
    .selectOption("published");
  await page.getByRole("button", { name: "Save event", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Event saved.");
  await logout(page);
  await signup(page, attendee, "attendee");
  await page.reload();
  await expect(
    page.getByRole("link", { name: "Alex", exact: true }),
  ).toBeVisible();
  await page.goto(eventPath);
  await page.getByRole("spinbutton", { name: "General quantity" }).fill("1");
  await page.getByRole("button", { name: "Reserve tickets" }).click();
  await expect(
    page.getByRole("heading", { name: "Your spot is on hold." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Complete demo payment" }).click();
  await expect(
    page.getByRole("heading", { name: "You’re going!" }),
  ).toBeVisible();
  const code = await page.locator(".order-ticket code").innerText();
  await page
    .getByRole("link", { name: "View my tickets", exact: true })
    .click();
  await expect(page.locator(".ticket-code code")).toHaveText(code);
  await page.goto(eventPath);
  await page.getByRole("spinbutton", { name: "General quantity" }).fill("1");
  await page.getByRole("button", { name: "Reserve tickets" }).click();
  await page.getByRole("button", { name: "Cancel reservation" }).click();
  await dialog.getByRole("button", { name: "Confirm cancellation" }).click();
  await expect(page.getByText("cancelled", { exact: true })).toBeVisible();
  await page.goto(eventPath);
  await expect(page.getByText("4 available", { exact: true })).toBeVisible();
  await logout(page);
  await login(page, organizer);
  await page.getByRole("link", { name: "Check-in", exact: true }).click();
  await page.getByLabel("Ticket code").fill(code);
  await page
    .getByRole("button", { name: "Check in ticket", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "You’re all set. Welcome in!" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Check in ticket", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(/already/i);
  expect(errors).toEqual([]);
});

test("cross-tab logout clears private content; attendee cannot enter organizer workspace", async ({
  page,
  context,
}) => {
  const secondEmail = `tabs-${Date.now()}@example.com`;
  await signup(page, secondEmail, "attendee");
  await page.goto("/tickets");
  await expect(
    page.getByRole("heading", { name: "Your tickets", exact: true }),
  ).toBeVisible();
  const other = await context.newPage();
  await other.goto("/profile");
  await expect(
    other.getByRole("heading", { name: "Your profile" }),
  ).toBeVisible();
  await other.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await expect(page.locator(".ticket-code")).toHaveCount(0);
  await login(page, secondEmail);
  await page.goto("/organizer");
  await expect(
    page.getByRole("heading", { name: "Organizer access required" }),
  ).toBeVisible();
  await other.close();
});

test("date filters preserve the selected local day and mobile navigation fits", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByText("Filters", { exact: true }).click();
  const filters = await page.locator(".filter-fields").boundingBox();
  expect(filters!.x).toBeGreaterThanOrEqual(0);
  await page.getByLabel("From date").fill("2027-10-10");
  await expect(page.getByLabel("From date")).toHaveValue("2027-10-10");
  await page.getByRole("button", { name: "Reset filters" }).click();
  await page.getByText("Filters", { exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Good plans. Great memories." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/mobile-home.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Developer API / Swagger" }).click();
  await expect(page.locator(".swagger-ui")).toBeVisible();
});

test("failed profile hydration after account switching never retains the old identity", async ({
  page,
}) => {
  await signup(page, `switch-${Date.now()}@example.com`, "attendee");
  await page.goto("/login");
  await expect(page.getByLabel("Email address")).toBeVisible();
  await page.route("**/api/auth/me/", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Profile temporarily unavailable" }),
    }),
  );
  await page.getByLabel("Email address").fill("organizer@demo.dev");
  await page.getByLabel("Password", { exact: true }).fill("demo-pass-123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Reconnect" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Alex", exact: true }),
  ).toHaveCount(0);
  await page.unroute("**/api/auth/me/");
  await page.getByRole("button", { name: "Reconnect" }).click();
  await expect(
    page.getByRole("button", { name: "Sign out", exact: true }),
  ).toBeVisible();
  await page.goto("/organizer");
  await expect(
    page.getByRole("link", { name: "Create event", exact: true }),
  ).toBeVisible();
});
