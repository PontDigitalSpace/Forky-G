"""
Metricool Client — Schedule posts via Metricool API
"""
import requests
import os
from datetime import datetime

BASE_URL = "https://app.metricool.com/api/v2"


class MetricoolClient:
    def __init__(self):
        # Metricool uses cookie-based auth from the MCP connection
        # For API use, we need the user token
        self.token = os.environ.get("METRICOOL_TOKEN", "")
        self.blog_id = os.environ.get("METRICOOL_BLOG_ID", "")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def schedule_post(
        self,
        text: str,
        media_urls: list,
        publish_date: str,   # "2026-06-03 07:00"
        platforms: list,     # ["instagram", "tiktok", "facebook"]
        post_type: str = "feed"  # feed, reel, story
    ) -> dict:
        """Schedule a post in Metricool."""
        dt = datetime.strptime(publish_date, "%Y-%m-%d %H:%M")

        payload = {
            "blogId": self.blog_id,
            "text": text,
            "publishDate": dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "networks": platforms,
            "type": post_type,
            "mediaUrls": media_urls
        }

        r = requests.post(
            f"{BASE_URL}/posts/schedule",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        r.raise_for_status()
        print(f"  ✅ Scheduled on {publish_date} → {', '.join(platforms)}")
        return r.json()

    def get_analytics(self, start_date: str, end_date: str) -> dict:
        """Get analytics data for a date range."""
        r = requests.get(
            f"{BASE_URL}/analytics",
            headers=self.headers,
            params={
                "blogId": self.blog_id,
                "from": start_date,
                "to": end_date
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()
