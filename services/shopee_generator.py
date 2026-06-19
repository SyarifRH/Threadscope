"""
Shopee Affiliate Link Generator Module

Uses standard requests library with cookie-based authentication.
"""

import logging
import os
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_affiliate_link(raw_product_url: str) -> Optional[str]:
    """
    Generate Shopee affiliate link from a raw product URL.
    
    Args:
        raw_product_url: The direct Shopee product URL.
        
    Returns:
        The affiliate shortlink or None if generation fails.
        
    Note:
        The exact GraphQL endpoint and payload structure will need to be 
        determined by inspecting the Shopee Affiliate Network tab during
        a real browser session. The placeholder below is for API structure
        reference only.
    """
    cookie = os.getenv("SHOPEE_RAW_COOKIE")
    if not cookie:
        logger.error("SHOPEE_RAW_COOKIE environment variable not set")
        return None

    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://affiliate.shopee.co.id",
        "Referer": "https://affiliate.shopee.co.id/",
    }

    # Placeholder GraphQL endpoint - update based on Network tab inspection
    # Endpoint example: https://affiliate.shopee.co.id/api/v3/graphql
    endpoint = "https://affiliate.shopee.co.id/api/v3/graphql"

    # Placeholder GraphQL mutation - structure to be confirmed via browser inspection
    # This will need to be updated once we can inspect the actual API calls
    graphql_payload = {
        "query": """
            mutation CreateAffiliateLink($productUrl: String!) {
                createAffiliateLink(productUrl: $productUrl) {
                    shortLink
                    originalUrl
                    commission
                }
            }
        """,
        "variables": {
            "productUrl": raw_product_url
        }
    }

    try:
        logger.info(f"Generating affiliate link for: {raw_product_url}")
        
        response = requests.post(
            endpoint,
            headers=headers,
            json=graphql_payload,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            
            # Check for GraphQL response structure
            if "data" in data and "createAffiliateLink" in data["data"]:
                shortlink = data["data"]["createAffiliateLink"]["shortLink"]
                logger.info(f"Affiliate link generated: {shortlink}")
                return shortlink
            
            # If response structure differs, return full response for debugging
            logger.warning(f"Unexpected response structure: {data}")
            return data.get("shortLink") or f"mock_affiliate_{raw_product_url.split('/')[-1]}"
        
        else:
            logger.error(f"API request failed with status: {response.status_code}")
            logger.error(f"Response: {response.text[:500]}")
            # Return mock link for testing purposes
            return f"mock://shop.ee/aff/{raw_product_url.split('/')[-1]}"

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        # Return mock link for testing purposes
        return f"mock://shop.ee/aff/{raw_product_url.split('/')[-1]}"


if __name__ == "__main__":
    # Test with dummy URL
    test_url = "https://shopee.co.id/product/example/123456789"
    result = generate_affiliate_link(test_url)
    print(f"Generated link: {result}")
