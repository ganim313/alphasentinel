---
template_id: "21"
phase: 5
assigned_role: "marketing/seo_engineer"
context_from: ["03_requirements_engineering.md", "11_go_to_market_analytics.md"]
outputs_to: ["07_deployment_runbook.md"]
status: template
---
# Template 21: Technical SEO Audit & Search Strategy

**Purpose:** To define the organic search engine optimization (SEO) architecture, schema taxonomy, meta tags, Core Web Vitals targets, and indexing strategy prior to production launch.

---

## 1. Executive SEO Strategy & Search Intent
Define the primary organic search targets, customer search intent (informational, transactional, navigational), and competitor search footprint.
- **Primary Target Audience:** `[Target customer profiles seeking this software solution]`
- **Core Value Proposition Keywords:** `[High-intent keyword clusters]`
- **Search Landscape:** `[Competitor ranking benchmarks & keyword gap analysis]`

## 2. Technical Site Architecture & Crawlability
Specify the technical crawling and indexing rules:
- **Canonical URLs:** `[Enforce strict https, non-www/www redirect policy, trailing slash normalization]`
- **Robots.txt Configuration:**
  ```txt
  User-agent: *
  Allow: /
  Disallow: /api/
  Disallow: /admin/
  Disallow: /private/
  Sitemap: https://[yourdomain.com]/sitemap.xml
  ```
- **XML Sitemap Strategy:** `[Dynamic sitemap generation via framework for static pages, blog posts, and dynamic product routes]`

## 3. On-Page Metadata & Schema.org Structured Data
Define JSON-LD schema markup templates and Open Graph standards:
- **Global Schema:** `Organization`, `WebSite`, `SoftwareApplication`
- **Product/Service Schema:** `Product`, `Offer`, `FAQPage`, `BreadcrumbList`
- **Social Graph Standards:** `og:title`, `og:description`, `og:image` (1200x630px), `twitter:card` (`summary_large_image`)

## 4. Core Web Vitals & Performance Targets
- **LCP (Largest Contentful Paint):** `< 2.5s`
- **INP (Interaction to Next Paint):** `< 200ms`
- **CLS (Cumulative Layout Shift):** `< 0.1`
- **Font & Asset Loading:** `[next/font or font-display: swap, image optimization via WebP/AVIF]`

## 5. Keyword Mapping Matrix

| Page / Route | Primary Keyword | Search Volume | Target Search Intent | Title Tag (`< 60 chars`) | Meta Description (`< 155 chars`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | `[Primary brand + category keyword]` | `[High]` | Commercial / Navigational | `[Title Tag String]` | `[Meta Description String]` |
| `/features` | `[Feature category keyword]` | `[Medium]` | Informational / Commercial | `[Title Tag String]` | `[Meta Description String]` |
| `/pricing` | `[Pricing & plan keyword]` | `[High]` | Transactional | `[Title Tag String]` | `[Meta Description String]` |

---

## ✍️ Human Lead Decision & Sign-Off Block
*(AI: You MUST pause here. Present the top 3 decisions made and wait for the human lead's explicit approval before proceeding.)*

* **Key Decision 1 (Keyword Focus):** `[Summary of targeted primary keyword clusters]`
* **Key Decision 2 (Schema Architecture):** `[Selected Schema.org structured data types]`
* **Key Decision 3 (Robots & Indexing):** `[Confirmation of crawl boundaries and sitemap generation]`

* **Human Lead Sign-Off:** ⏳ Awaiting Approval / ✅ Approved / 🔄 Revisions Requested
* **Human Overrides / Adjustments:** `[Type 'Approved' or enter adjustments]`

---

## Agent Handoff to Next Phase

### Pre-Flight Checks
- [ ] Schema markup validated against Google Rich Results Test.
- [ ] Open Graph and Twitter Card tags configured with fallback preview images.
- [ ] No unresolved placeholders (`[TBD]`, `[ ]`) in metadata matrix.
- [ ] Human Lead has explicitly signed off above.

### Context Package for Next Agent
- [ ] 21_seo_audit_strategy.md