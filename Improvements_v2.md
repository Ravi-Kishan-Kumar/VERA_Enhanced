# Improvements v2 — Implementation Plan

> [!IMPORTANT]
> **Zero API Key Requirement Confirmed:**  
> We are using **DuckDuckGo Search (`duckduckgo_search`)** to query live Indian market data (Amazon India, Flipkart, Croma, RTINGS, TechRadar, 91mobiles).  
> - **Cost:** 100% Free  
> - **Setup:** Zero API keys, zero accounts, zero credit cards  
> - **Quotas:** No monthly search limit  
> - **Locale:** Targeted specifically for India (`region='in-en'`, INR ₹ prices)

---

## 1. Insights — Hardware & Acoustic Comparative Matrix (Option B)

### Replacement
Replace the complex statistical sentiment delta matrix with the direct, intuitive **Hardware & Acoustic Engineering Comparison Matrix**:

| Aspect | Usually Better | Engineering & Acoustic Rationale |
| :--- | :--- | :--- |
| **Sound Quality** | 🎧 **Headphones** | Larger drivers (40–50mm vs 6–12mm), wider acoustic soundstage, natural air resonance, and more room for acoustic tuning. Premium earbuds come close. |
| **Bass** | 🎧 **Headphones** | Bigger drivers physically move more air mass for true sub-bass rumble without distortion. Earbuds can still sound punchy if silicone tips seal tightly. |
| **Battery Life** | 🎧 **Headphones** | Typically 20 to 60 hours continuous listening on a single charge, against 5 to 8 hours per earbud charge (charging case adds 20 to 30 hours). |
| **Comfort** | ⚖️ **Depends** | Earbuds are ultralight and cool, but cause in-ear canal fatigue. Over-ear headphones suit long desk sessions but get warm and can have headband clamping pressure. |
| **Fit** | 🤝 **Tie** | Headphones fit more people with minimal adjustment. Earbuds depend on ear canal shape and tip sizing, though sport models with wings stay locked during runs. |
| **Build Quality** | 🎧 **Headphones** | Sturdier chassis materials, replaceable ear cushions/cables, and longer lifespan. Earbuds are tiny, easy to misplace, and non-replaceable miniature batteries wear out faster. |
| **Connectivity** | 🤝 **Tie** | Earbuds frequently ship with the newest Bluetooth LE standards. Headphones add true multipoint switching, zero-latency wired fallback, and 3.5mm / USB-C audio jacks. |
| **Microphone** | 🎧 **Headphones** | Larger acoustic chambers and optional boom mics deliver vastly clearer speech. Earbud microphones sit far from the mouth, though beamforming has improved them. |
| **Noise Cancellation** | 🎧 **Headphones** | Full ear cups physically isolate ambient noise (especially low-frequency drone/cabin rumble) combined with multi-mic ANC arrays. Top-tier earbuds are close with deep seals. |
| **Value for Money** | ⚖️ **Depends** | Earbuds offer more compelling budget choices (< ₹2,500). Headphones deliver noticeably more acoustic depth, durability, and battery per rupee in the mid-range (₹3,000–₹10,000). |

**Key Takeaway Card:**
> 💡 *Earbuds win when you need pocketable, gym-friendly, or lightweight gear on the go. Headphones win for long listening sessions, critical calls, studio fidelity, and maximum noise blocking.*

### Files Changed:
- `frontend/src/components/vera/insights-hub.tsx`

---

## 2. Product Rankings Table — Column Width & Overflow Fix

### Problem
Long product titles (e.g., *"Sony WH-1000XM5 Wireless Industry Leading Noise Canceling Headphones with Auto NC Optimizer..."*) overflow the `Product` column and visually bleed into the `VERA Score` column.

### Implementation Changes
1. Apply `table-fixed w-full` to the `<Table>` component.
2. Define explicit column widths:
   - **Rank:** `w-[70px] min-w-[70px]`
   - **Product:** `w-[320px] max-w-[320px] overflow-hidden`
   - **VERA Score:** `w-[130px] min-w-[130px]`
   - **Uncertainty & Reviews:** `w-[140px] min-w-[140px]`
   - **Signals:** `w-[180px] min-w-[180px]`
   - **Actions (Compare):** `w-[100px] min-w-[100px]`
3. Wrap product titles in a constrained flexbox with `truncate block font-medium` and a tooltip for the full product title on hover.

### Files Changed:
- `frontend/src/components/vera/product-rankings.tsx`

---

## 3. Advisor — Live Web Market Recommendations (DuckDuckGo Zero-Key)

### Capabilities
- Real-time search of Indian e-commerce (Amazon.in, Flipkart, Croma) and audio review consensus via DuckDuckGo (`region='in-en'`).
- Ranks live models based on user interest sliders (Audio, ANC, Bass, Battery, Comfort, Mic, Latency, Value).
- Returns:
  - **Top 5 for Budget Bracket (< ₹2,500)**
  - **Top 5 for Mid-Range Bracket (₹2,500 – ₹8,000)**
  - **Top 5 for Premium Bracket (> ₹8,000)**
  - **Overall Top 3 in India**
- Each product card contains: Title, Price in ₹, Star Rating, Merchant tag, Direct purchase/view link, and Aspect match badge.

### Files Changed:
- `backend/app/services/web_search.py` (New service)
- `backend/app/api/routes/advisor.py` (New `/web-recommend` endpoint)
- `frontend/src/components/vera/product-advisor.tsx` (Live Web Market toggle & cards)

---

## 4. Product Comparison — Open Web Comparison (DuckDuckGo Zero-Key)

### Capabilities
- Free-form text comparison allowing users to compare **any two products** from the web (e.g., "Sony WH-1000XM5" vs "Bose QuietComfort 45").
- Fetches real-world specs, pricing across Indian retailers (Amazon, Flipkart, Croma), customer review consensus, and pros/cons.
- Displays:
  - Side-by-side header cards with pricing and merchant links.
  - Head-to-Head Aspect Winner badges (Sound, ANC, Battery, Comfort, Mic, Value).
  - Detailed Specifications table (Drivers, Battery with ANC, Codecs, Weight, Fast Charging).
  - Pros & Cons bullet points extracted from customer reviews.

### Files Changed:
- `backend/app/api/routes/compare.py` (New route file)
- `backend/app/main.py` (Register router)
- `frontend/src/components/vera/compare-view.tsx` (Free-form search & web compare cards)

---

## Execution Order
1. **Insights Tab:** Implement Option B (Hardware & Acoustic Matrix + Takeaway card).
2. **Product Rankings:** Fix column width, overflow, and table layout.
3. **DuckDuckGo Web Search Service:** Build backend search & parsing engine.
4. **Advisor Web Recommendations:** Add `/api/advisor/web-recommend` and connect frontend.
5. **Open Web Compare:** Implement `/api/compare/web` and redesign compare UI.
6. **Validation:** Run automated checks and browser tests.
