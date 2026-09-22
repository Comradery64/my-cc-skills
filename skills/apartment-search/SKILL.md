---
name: apartment-search
description: Search for apartments matching the user's criteria. Researches local market rates, scrapes live Craigslist listings, deep-dives promising listings, scores each for legitimacy/scam risk, and outputs a ranked table with confidence scores and key details.
---

The user wants to search for apartments. Extract these parameters from their message:
- **Bedrooms**: number of bedrooms (default: 1)
- **Location**: city or zip code to center the search
- **Max price**: maximum monthly rent
- **Radius**: search radius in miles (default: 15)

---

## Phase 1 — Market Context

Run **3 WebSearch queries in parallel**:
1. `average [N] bedroom apartment rent [CITY] [CURRENT_YEAR]`
2. `average 1BR rent [NEARBY_CITY_1] [NEARBY_CITY_2] [NEARBY_CITY_3] [CURRENT_YEAR]`
3. `cities within [RADIUS] miles of [CITY] [STATE] affordable rentals`

Summarize:
- Average 1BR rent for the target city and key nearby cities
- How far the user's budget is above/below market (%)
- What that gap implies (rare finds, scam-heavy pool, rooms-only, etc.)

Show as a compact table before proceeding.

---

## Phase 2 — Scrape Listings

Use `dev-browser` (headless) to scrape Craigslist for the target area. Use the appropriate Craigslist subdomain for the region (e.g. `sfbay`, `losangeles`, `chicago`, `newyork`).

```javascript
// Search URL pattern (sort=date ensures newest-first; without it Craigslist uses "best match" which buries fresh listings):
// https://[subdomain].craigslist.org/search/apa?min_price=&max_price=[MAX]&min_bedrooms=[N]&max_bedrooms=[N]&postal=[ZIP]&search_distance=[RADIUS]&sort=date

const data = await page.evaluate(() => {
  const results = [];
  document.querySelectorAll('.cl-search-result').forEach(el => {
    const pid = el.getAttribute('data-pid');
    const title = el.getAttribute('title') || '';
    const link = el.querySelector('a.main')?.href || '';
    const price = el.querySelector('.priceinfo')?.textContent?.trim() || '';
    const bedrooms = el.querySelector('.post-bedrooms')?.textContent?.trim() || '';
    const sqft = el.querySelector('.post-sqft')?.textContent?.trim() || '';
    const location = el.querySelector('.result-location')?.textContent?.trim() || '';
    const date = el.querySelector('.result-posted-date')?.textContent?.trim() || '';
    const hasImages = !el.querySelector('.cl-gallery.empty');
    if (pid) results.push({ pid, title, price, bedrooms, sqft, location, date, link, hasImages });
  });
  return results;
});
```

If the ZIP code isn't known, do a quick WebSearch first to find the correct ZIP for the city center.

**Filter candidates** before deep-diving:
- Within the stated radius (use location field + market knowledge)
- Price at or below max budget
- Labeled as the correct bedroom count
- Not obviously spam (e.g. repeated PIDs, "interest list", senior communities if user isn't 55+)

Select the **top 10-15 most promising candidates** for deep-dive. Prefer listings that are geographically closest to the target city.

---

## Phase 3 — Deep-Dive & Scam Analysis

Batch-fetch detail pages for all selected candidates in a single `dev-browser` session:

```javascript
// For each URL, extract:
{
  title, price, attrs,   // attrs = .attrgroup spans
  mapAddr,               // .mapaddress
  body,                  // #postingbody (first 1500 chars)
  imageCount,            // count of #thumbs a
  postDate,              // time.date[datetime]
  url
}
```

**Score each listing 0–100** using this rubric:

| Signal | Points |
|--------|--------|
| Start | 50 |
| Photos: 15+ | +15 |
| Photos: 5–14 | +10 |
| Photos: 1–4 | +5 |
| No photos | -20 |
| Specific street address | +10 |
| Named complex/building | +5 |
| Named property manager | +5 |
| Clear lease terms (duration, what's included) | +10 |
| Professional description, unique details | +10 |
| Application fee mentioned (standard practice) | +5 |
| Posted today or recently | +5 |
| Price >40% below market avg | -20 |
| Price 25–40% below market avg | -10 |
| Price 10–25% below market avg | -5 |
| "Bedr00m" or other filter-evasion | -15 |
| No address at all | -15 |
| Shared unit (room in house, not full apt) | -25 |
| Not actually the right bedroom count | -20 |
| Obvious template/copy-paste description | -15 |
| Mass-poster (same person, 5+ identical listings) | -10 |
| Price is so low it's implausible (>60% below market) | -30 |
| Senior-only community (if user doesn't qualify) | -40 |

**Confidence tiers:**
- **90–100**: GREEN — high confidence, schedule a visit
- **75–89**: YELLOW-GREEN — likely legitimate, verify before applying
- **60–74**: YELLOW — proceed with caution, verify identity
- **40–59**: ORANGE — significant red flags
- **0–39**: RED — likely scam or misrepresented listing

---

## Phase 4 — Output

Show a **budget warning** if max price is more than 20% below market average for the target city.

Then output listings sorted by confidence score (highest first), grouped by tier. For each listing include:

```
[Rank]. [Complex Name or Title] — [City] | $[Price]/mo | Confidence: [Score]/100
────────────────────────────────────────────
Price:      $X/mo
Size:       [sqft], [BR/Ba]
Location:   [address or area], [city] (~[N] mi from [TARGET])
Available:  [date or "now"]
Link:       [craigslist URL]

Why [high/moderate/low] confidence:
• [bullet 1]
• [bullet 2]

Yellow/Red flags:
• [flag 1]
```

After all listings, include a **"What to do next"** section:
- For top GREEN listings: schedule a tour, verify property manager via Google, never wire money before seeing in person
- For YELLOW listings: call or text (don't just email), ask for a physical tour, reverse-image-search photos
- For any listing: never pay deposit before signing a lease, never use Zelle/Venmo/wire for initial payment

If fewer than 3 listings scored above 70, note that the budget is likely too low for the target area and suggest either increasing the budget or expanding the radius, with specific numbers based on the market context gathered in Phase 1.
