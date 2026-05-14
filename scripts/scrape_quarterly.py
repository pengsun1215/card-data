#!/usr/bin/env python3
"""
Scrape 5% quarterly cash back categories for Chase Freedom Flex and Discover It.
Uses Claude API to extract structured data from HTML pages.

Sources:
  - Chase: https://www.chasebonus.com
  - Discover: https://www.discover.com/credit-cards/cash-back/cashback-calendar.html

Usage:
  pip install requests beautifulsoup4 anthropic
  export ANTHROPIC_API_KEY=sk-...
  python scrape_quarterly.py
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

# Known spending categories in the app
VALID_CATEGORIES = [
    "Dining", "Grocery", "Amazon", "Travel", "Gas",
    "Streaming", "Drugstore", "Home Improv", "Everything Else"
]

EXTRACTION_PROMPT = """Extract the 5% cash back rotating categories for each quarter (Q1 through Q4) from the following web page content.

Map each category to one of these exact app categories when possible:
{categories}

If a category doesn't map cleanly (e.g. "Walmart" or "Target"), keep the original name as-is.

Return ONLY valid JSON in this exact format:
{{
  "year": 2026,
  "quarters": {{
    "1": {{"categories": ["Gas", "EV Charging"], "raw_description": "original text from page"}},
    "2": {{"categories": ["Grocery"], "raw_description": "original text from page"}},
    "3": {{"categories": ["Dining"], "raw_description": "original text from page"}},
    "4": {{"categories": ["Amazon", "Streaming"], "raw_description": "original text from page"}}
  }}
}}

If a quarter's categories are not yet announced, set categories to [] and raw_description to "Not yet announced".

Web page content:
{content}
"""


def fetch_page(url: str, max_chars: int = 30000) -> str:
    """Fetch a web page and extract text content."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script/style tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    return text[:max_chars]


def extract_categories_with_llm(page_text: str, card_name: str) -> dict:
    """Use Claude API to extract quarterly categories from page text."""
    client = anthropic.Anthropic()

    prompt = EXTRACTION_PROMPT.format(
        categories=json.dumps(VALID_CATEGORIES),
        content=page_text
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"This page is about {card_name} 5% cash back calendar.\n\n{prompt}"
        }]
    )

    # Extract JSON from response
    text = response.content[0].text
    # Find JSON block (might be wrapped in ```json ... ```)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    return json.loads(text.strip())


def scrape_chase() -> dict:
    """Scrape Chase Freedom Flex quarterly categories."""
    url = "https://www.chasebonus.com"
    print(f"Fetching {url} ...")
    try:
        page_text = fetch_page(url)
        print(f"  Got {len(page_text)} chars of text")
        result = extract_categories_with_llm(page_text, "Chase Freedom Flex")
        print(f"  Extracted: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"  Error scraping Chase: {e}")
        return {"year": date.today().year, "quarters": {}, "error": str(e)}


def scrape_discover() -> dict:
    """Scrape Discover It quarterly categories."""
    url = "https://www.discover.com/credit-cards/cash-back/cashback-calendar.html"
    print(f"Fetching {url} ...")
    try:
        page_text = fetch_page(url)
        print(f"  Got {len(page_text)} chars of text")
        result = extract_categories_with_llm(page_text, "Discover It")
        print(f"  Extracted: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"  Error scraping Discover: {e}")
        return {"year": date.today().year, "quarters": {}, "error": str(e)}


def main():
    # Determine output path
    script_dir = Path(__file__).parent
    repo_dir = script_dir.parent
    output_path = repo_dir / "quarterly_categories.json"

    # Load existing data if present
    existing = {}
    if output_path.exists():
        with open(output_path) as f:
            existing = json.load(f)

    print("=== Scraping 5% Quarterly Categories ===\n")

    chase_data = scrape_chase()
    print()
    discover_data = scrape_discover()

    # Build output
    output = {
        "version": existing.get("version", 0) + 1,
        "lastUpdated": date.today().isoformat(),
        "chase_freedom_flex": chase_data,
        "discover_it": discover_data
    }

    # Write output
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWritten to {output_path}")
    print(f"Version: {output['version']}")


if __name__ == "__main__":
    main()
