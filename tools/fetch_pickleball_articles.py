#!/usr/bin/env python3
"""
Automated Pickleball Article Fetcher for Pickleball Finder (Pro Trainer Hub)

Pulls the latest pickleball articles, tips, gear guides, and tournament news from
trusted RSS feeds and updates both trainer/newsletters.csv and trainer/newletters.csv.
Uses standard Python library only (zero external pip dependencies).
"""

import csv
import datetime
import email.utils
import html
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = [
    {
        "name": "The Dink",
        "url": "https://www.thedinkpickleball.com/feed/",
        "default_category": "Strategy",
    },
    {
        "name": "Pickleball Union",
        "url": "https://pickleballunion.com/feed/",
        "default_category": "News & Tips",
    },
]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def clean_text(raw_text: str) -> str:
    """Removes HTML tags, decodes HTML entities, and normalizes whitespace."""
    if not raw_text:
        return ""
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", raw_text)
    # Decode HTML entities like &#8217; &amp; &nbsp;
    clean = html.unescape(clean)
    # Strip weird brackets/citations
    clean = re.sub(r"\[\.\.\.\]", "", clean)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

def detect_category(title: str, summary: str, fallback: str) -> str:
    """Assigns category matching TrainerScreen icons and filters."""
    combined = f"{title} {summary}".lower()

    if re.search(r"\b(injur\w*|ankle|elbow|knee|fitness|health|warm\s*up|stretch\w*|rehab\w*|pain|therapy)\b", combined):
        return "Health & Fitness"
    if re.search(r"\b(paddles?|gear|grips?|shoes?|carbon fiber|reviews?|equipment)\b", combined):
        return "Rules & Gear"
    if re.search(r"\b(ppa|mlp|tour\w*|troph\w*|championship\w*|ben johns|waters|medal\w*|grand slam)\b", combined):
        return "Pro Tour"
    if re.search(r"\b(rules?|faults?|serve rule\w*|compliance|kitchen rule\w*|line call\w*|referee\w*)\b", combined):
        return "Rules"
    if re.search(r"\b(dink\w*|kitchen|drop\w*|reset\w*|drive\w*|third shot|strateg\w*|tactic\w*|court position|technique|backhand|forehand|shot)\b", combined):
        return "Strategy"

    return fallback or "Strategy"

def parse_pub_date(pub_date_str: str) -> tuple:
    """Parses RFC-822 date format into a sortable timestamp and display month string."""
    try:
        parsed_tuple = email.utils.parsedate_to_datetime(pub_date_str)
        timestamp = parsed_tuple.timestamp()
        display_date = parsed_tuple.strftime("%b %Y")
        return timestamp, display_date
    except Exception:
        now = datetime.datetime.now()
        return now.timestamp(), now.strftime("%b %Y")

def fetch_feed(feed_info: dict) -> list:
    """Fetches and parses a single RSS feed."""
    url = feed_info["url"]
    source_name = feed_info["name"]
    articles = []

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read()
            root = ET.fromstring(content)

            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                pub_elem = item.find("pubDate")

                if title_elem is None or not title_elem.text:
                    continue

                title = clean_text(title_elem.text)
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                desc = clean_text(desc_elem.text) if desc_elem is not None and desc_elem.text else ""
                pub_str = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

                if not link or not title:
                    continue

                # Shorten long descriptions to ~180 chars cleanly at word boundary
                if len(desc) > 190:
                    cutoff = desc[:180].rfind(" ")
                    summary = (desc[:cutoff] if cutoff > 120 else desc[:180]).strip() + "..."
                else:
                    summary = desc or f"Read the latest {title} update from {source_name}."

                timestamp, display_date = parse_pub_date(pub_str)
                category = detect_category(title, summary, feed_info["default_category"])

                # Estimated read time (assuming ~180 words/min average)
                words = len(desc.split())
                read_time = f"{max(3, min(7, (words // 40) + 3))} min read"

                articles.append({
                    "title": title,
                    "category": category,
                    "summary": summary,
                    "source": source_name,
                    "read_time": read_time,
                    "date": display_date,
                    "url": link,
                    "_timestamp": timestamp,
                })
    except Exception as e:
        print(f"Warning: Failed to fetch {url}: {e}", file=sys.stderr)

    return articles

def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_files = [
        os.path.join(repo_root, "trainer", "newsletters.csv"),
        os.path.join(repo_root, "trainer", "newletters.csv"),
    ]

    all_articles = []
    for feed in FEEDS:
        print(f"Fetching {feed['name']}...")
        articles = fetch_feed(feed)
        print(f"  -> Found {len(articles)} articles")
        all_articles.extend(articles)

    if not all_articles:
        print("Error: No articles could be fetched from any source. Keeping existing files.", file=sys.stderr)
        sys.exit(1)

    # Sort newest first
    all_articles.sort(key=lambda x: x["_timestamp"], reverse=True)

    # Deduplicate by normalized title
    seen_titles = set()
    unique_articles = []
    for art in all_articles:
        norm_title = re.sub(r"[^a-z0-9]", "", art["title"].lower())
        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            unique_articles.append(art)

    # Select top 7 latest articles
    selected = unique_articles[:7]

    print(f"\nWriting {len(selected)} articles:")
    for a in selected:
        print(f" • [{a['category']}] {a['title']} ({a['source']} - {a['date']})")

    headers = ["title", "category", "summary", "source", "read_time", "date", "url"]

    for file_path in target_files:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            for a in selected:
                writer.writerow([
                    a["title"],
                    a["category"],
                    a["summary"],
                    a["source"],
                    a["read_time"],
                    a["date"],
                    a["url"],
                ])
        print(f"Successfully updated: {file_path}")

if __name__ == "__main__":
    main()
