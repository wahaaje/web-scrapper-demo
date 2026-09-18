# Site configuration

Start from `examples/site-config.example.json`. Copy it to `config.local.json`, which is ignored by Git. All selectors and URLs in that example are placeholders; `examples/demo.json` is the working configuration for the bundled fixtures.

## Schema

| Key | Type | Default / requirement |
|---|---|---|
| `listing_url` | string | Required absolute HTTP(S) URL, without embedded credentials |
| `link_selector` | string | Required CSS selector for detail links with `href` attributes |
| `fields` | object | Required mapping of output field names to CSS selectors |
| `required_fields` | array | `["name"]`; every entry must appear in `fields` |
| `next_selector` | string or null | `null`; matching next-page anchor, if pagination exists |
| `listing_ready` | string | `body`; element to wait for before reading the listing snapshot |
| `detail_ready` | string | `body`; element to wait for before reading a detail snapshot |
| `block_selector` | string | `.data-block`; repeated section container |
| `block_label` | string | `.block-label`; label selector inside each section |
| `block_value` | string | `.block-value`; value selector inside each section |
| `request_delay` | number | `1.5`; 1–120 seconds between page attempts; demo skips sleeping |
| `timeout` | number | `20`; 1–300 seconds for navigation, and separately for the explicit wait |
| `retries` | integer | `1`; 0–3 additional attempts for timeouts only |
| `max_listing_pages` | integer | `10`; 1–500 listing pages per run |

Unknown keys, invalid CSS syntax, inconsistent required fields and invalid numeric settings fail before Chrome starts. Use standard browser-compatible CSS selectors for the two `*_ready` waits. Parsing selectors are implemented with Beautiful Soup and SoupSieve.

Field names must start with a lowercase letter and contain only lowercase letters, digits and underscores, up to 40 characters. Metadata names (`requested_url`, `source_url`, `scraped_at`, `status`, `attempts`, `issues`) are reserved.

## Choosing waits and fields

Set `listing_ready` to the loaded listing container and `detail_ready` to the loaded detail container. Waiting on `body` alone may capture a JavaScript page before its data arrives. An element's presence does not guarantee every field has finished updating; choose a reliable ready marker for that site.

Field extraction uses the first matching element. It trims text runs and joins them with spaces; it does not extract an element's `href`, infer an absent email, reformat a phone number or evaluate computed CSS visibility. Use a selector that points to the actual text node/container you need.

If a site has no repeated sections, leave the block selectors unchanged or set `block_selector` to an appropriate selector that matches nothing. No matching blocks is valid. A matched block with an empty label or value is retained and marks the record `partial`.

## Links and scope

Relative URLs are resolved against the loaded page URL, including parent-relative and protocol-relative links. Fragments are removed, default ports normalized and query strings preserved. Detail links outside the starting origin are skipped. Pagination links outside that origin cause a clear error.

The next-page selector must match an anchor with an in-scope `href`. An absent next link, or an anchor with `aria-disabled="true"`, ends pagination. Buttons that load results without changing an `href` need a custom adapter.

The limit is controlled by `--limit` (default 15, maximum 5000). Reaching either a record or page cap is recorded as a warning, even if the cap happens to equal the site's size. It does not imply that every available record was collected.

## Record example

```json
{
  "requested_url": "https://demo.test/records/atlas.html",
  "source_url": "https://demo.test/records/atlas.html",
  "scraped_at": "2026-09-18T10:00:00+00:00",
  "fields": {"name": "Atlas Studio", "category": "Design"},
  "blocks": [
    {"label": "Service", "value": "Brand identity"},
    {"label": "Service", "value": "Editorial design"}
  ],
  "status": "ok",
  "attempts": 1,
  "issues": []
}
```

This abbreviated example shows the shape. The [generated fixture JSON](../examples/output/records.json) contains the full fields and all sections.
