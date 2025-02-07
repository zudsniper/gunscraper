import os
from pathlib import Path
import json
from dotenv import load_dotenv
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.utils import prettify_exec_info
from models import ListingPreviews, ListingsPages, ListingsPage
from pydantic import BaseModel, Field
from datetime import datetime
import traceback
from langchain_community.chat_models import ChatOpenAI
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_result
import time

listing_page_prompt = """
Extract all listings from this page. 
For each listing, identify the type of item(s) and extract relevant information:

- title
- price
- description
- items: List of items in the listing, each with:
    - item_type: gun, magazine, ammunition, optic, light, holster, body_armor, or other
    - manufacturer
    - model
    - caliber (for guns, magazines, ammunition)
    - condition (for guns)
    - capacity (for magazines)
    - quantity (for ammunition)
- image_urls
- listing_url
"""

class LLMProvider(str, Enum):
    OPENROUTER = "openrouter"
    LANGCHAIN = "langchain"

def get_graph_config(
    provider: LLMProvider = LLMProvider.OPENROUTER,
    model: str = "openai/gpt-4o-mini",
    model_instance: Optional[Any] = None,
    verbose: bool = True,
    headless: bool = False,
    use_proxy: bool = True,
    **kwargs
) -> Dict:
    """
    Get configuration for SmartScraperGraph based on provider type
    
    Args:
        provider: LLM provider to use (openrouter or langchain)
        model: Model identifier (for OpenRouter)
        model_instance: Pre-configured LangChain model instance
        verbose: Enable verbose logging
        headless: Run browser in headless mode
        use_proxy: Whether to use proxy settings from env
        **kwargs: Additional configuration options
    
    Returns:
        Dictionary containing graph configuration
    """
    
    # Base configuration
    config = {
        "verbose": verbose,
        "headless": headless,
        "browser_name": "chromium",
        "backend": "undetected_chromedriver",
    }
    
    # Add proxy configuration if enabled
    if use_proxy:
        proxy_server = os.getenv("PROXY_SERVER")
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        
        if proxy_server and proxy_username and proxy_password:
            config["loader_kwargs"] = {
                "proxy": {
                    "server": proxy_server,
                    "username": proxy_username,
                    "password": proxy_password,
                }
            }
    
    # Add provider-specific LLM configuration
    if provider == LLMProvider.OPENROUTER:
        config["llm"] = {
            "api_key": os.getenv("OPENROUTER_KEY"),
            "model": model,
            "base_url": "https://openrouter.ai/api/v1",
        }
    
    elif provider == LLMProvider.LANGCHAIN:
        if not model_instance:
            # Default to OpenAI via LangChain if no instance provided
            model_instance = ChatOpenAI(
                openai_api_key=os.getenv("OPENROUTER_KEY"),
                openai_api_base="https://openrouter.ai/api/v1",
                model_name=model
            )
        
        config["llm"] = {
            "model_instance": model_instance,
            "model_tokens": kwargs.get("model_tokens", 4096)  # Default token limit
        }
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    
    # Add any additional configuration
    config.update(kwargs)
    
    return config

def get_page_count(url: str, config: dict) -> tuple[int, dict]:
    """Get total page count, either from cache or by scraping"""
    cache_file = Path("page_count_cache.json")
    
    # Check cache first
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            print("Using cached page count")
            return cached["page_count"], cached["execution_info"]
    
    # If not cached, scrape it
    get_last_page_prompt = """
    Find the last page number from the pagination buttons at the bottom of the page. (total_pages)
    Return only the highest page number you find.
    """

    class PageCount(BaseModel):
        total_pages: int = Field(description="The highest page number found in the pagination")
    
    smart_scraper_graph = SmartScraperGraph(
        prompt=get_last_page_prompt,
        source=url,
        config=config,
        schema=PageCount
    )

    page_count_result = smart_scraper_graph.run()
    page_count = page_count_result["total_pages"]
    
    exec_info = smart_scraper_graph.get_execution_info()
    
    # Cache the result
    with open(cache_file, 'w') as f:
        json.dump({
            "page_count": page_count,
            "execution_info": exec_info,
            "cached_at": datetime.now().isoformat()
        }, f, indent=4)
    
    return page_count, exec_info

def create_result_template(url: str, start_time: datetime) -> dict:
    """Create the initial result dictionary"""
    return {
        "start_time": start_time.isoformat(),
        "url": url,
        "status": "started",
        "last_completed_page": None,
        "error": None,
        "execution_info": [],
        "data": None,
        "end_time": None,
        "duration_seconds": None
    }

def save_progress(result: dict, start_time: datetime, output_path: Path = Path("scraping_results.json")):
    """Save current progress to file"""
    result["end_time"] = datetime.now().isoformat()
    result["duration_seconds"] = (datetime.now() - start_time).total_seconds()
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=4)
    print(f"\nProgress saved to {output_path}")

def is_empty_listings(result: Tuple[Any, Dict]) -> bool:
    """Check if the listings result is empty or invalid"""
    listing_previews, _ = result
    
    # Check if we got a valid response
    if not listing_previews:
        print("Got null response")
        return True
        
    # Check if it's a dict (raw response) instead of parsed model
    if isinstance(listing_previews, dict):
        try:
            # Check if the dict has valid listings
            listings = listing_previews.get('listings', [])
            if listings and len(listings) > 0:
                print(f"Found {len(listings)} listings in raw dict")
                return False
        except Exception as e:
            print(f"Error checking raw dict listings: {str(e)}")
        print("Got empty or invalid raw dict")
        return True
        
    # Check if listings exist and aren't empty
    try:
        listings_count = len(listing_previews.listings)
        print(f"Found {listings_count} listings")
        return listings_count == 0
    except (AttributeError, TypeError) as e:
        print(f"Error checking listings: {str(e)}")
        return True

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_result(is_empty_listings)
)
def scrape_page(page_url: str, graph_config: Dict) -> Tuple[Optional[ListingPreviews], Dict]:
    """
    Scrape a single page with retry logic
    
    Returns:
        Tuple of (ListingPreviews, execution_info)
    """
    print(f'Attempting to scrape {page_url}')
    
    try:
        smart_scraper_graph = SmartScraperGraph(
            prompt=listing_page_prompt,
            source=page_url,
            config=graph_config,
            schema=ListingPreviews,
        )

        listing_previews = smart_scraper_graph.run()
        exec_info = smart_scraper_graph.get_execution_info()
        
        if not listing_previews:
            print("No listings found, will retry...")
            return None, exec_info
            
        # Ensure we have a ListingPreviews model
        if isinstance(listing_previews, dict):
            try:
                listing_previews = ListingPreviews(**listing_previews)
            except Exception as e:
                print(f"Error converting dict to ListingPreviews: {str(e)}")
                return None, exec_info
            
        if not listing_previews.listings:
            print("Empty listings found, will retry...")
            
        return listing_previews, exec_info
        
    except Exception as e:
        print(f"Error during page scrape: {str(e)}")
        return None, {}

def run_scraper(url: str, result: dict, start_time: datetime, graph_config: Optional[Dict] = None) -> dict:
    """Run scraper for a single URL"""
    output_path = Path("scraping_results.json")
    start_page = 1
    execution_info = []
    
    if output_path.exists():
        with open(output_path, 'r') as f:
            previous_run = json.load(f)
            if previous_run["status"] == "failed" and previous_run["last_completed_page"]:
                start_page = previous_run["last_completed_page"] + 1
                execution_info = previous_run["execution_info"]
                print(f"Resuming from page {start_page}")
    
    # Use default OpenRouter config if none provided
    if graph_config is None:
        graph_config = get_graph_config(use_proxy=True)

    # Get page count (cached or fresh)
    last_page, exec_info = get_page_count(url, graph_config)
    if not execution_info:  # Only append if starting fresh
        execution_info = [exec_info]
    print(f'Found {last_page} total pages')

    # Generate all page URLs
    base_url = "https://austin.texasguntrader.com/category/548/For-Sale-Trade/"
    pages = ListingsPages(pages=[], num_pages=last_page)
    
    # Load existing pages if resuming
    if start_page > 1 and output_path.exists():
        with open(output_path, 'r') as f:
            previous_run = json.load(f)
            if previous_run["data"]:
                pages.pages = [ListingsPage(**page) for page in previous_run["data"]["pages"][:start_page-1]]
    
    # Scrape each page
    for page_num in range(start_page, last_page + 1):
        page_url = f"{base_url}{page_num}.html"
        print(f'Scraping page {page_num} of {last_page}')
        
        try:
            listing_previews, exec_info = scrape_page(page_url, graph_config)
            execution_info.append(exec_info)
            
            new_page = ListingsPage(
                page_url=page_url,
                page_number=page_num,
                listing_previews=listing_previews
            )
            pages.pages.append(new_page)
            
            # Update result data and save progress
            result["data"] = pages.model_dump()
            result["last_completed_page"] = page_num
            save_progress(result, start_time)
            
            # Use prettify_exec_info for better formatting
            print(prettify_exec_info(exec_info))
            print('done, next page...')
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {str(e)}")
            print("Continuing to next page...")
            continue

    return {
        "result": pages.model_dump(),
        "execution_info": execution_info
    }

def main():
    start_time = datetime.now()
    # Load environment variables
    load_dotenv()
    
    url = "https://austin.texasguntrader.com/GUNS-FOR-SALE/548/For-Sale-Trade.html"
    result = create_result_template(url, start_time)
    
    # Example configurations:
    
    # 1. Default OpenRouter config with proxy
    default_config = get_graph_config(use_proxy=False)
    
    # 2. OpenRouter with different model and proxy
    gpt4_config = get_graph_config(
        model="openai/gpt-4-turbo-preview",
        temperature=0.7,
        use_proxy=False
    )
    
    # 3. LangChain with custom model and proxy
    # from langchain_community.chat_models.moonshot import MoonshotChat
    # moonshot_model = MoonshotChat(
    #     model="moonshot-v1-8k",
    #     base_url="https://api.moonshot.cn/v1",
    #     moonshot_api_key=os.getenv("MOONSHOT_API_KEY")
    # )
    # moonshot_config = get_graph_config(
    #     provider=LLMProvider.LANGCHAIN,
    #     model_instance=moonshot_model,
    #     model_tokens=8192,
    #     use_proxy=True
    # )
    
    try:
        print(f"Processing URL: {url}")
        # Choose which config to use
        scrape_result = run_scraper(url, result, start_time, graph_config=default_config)
        
        result["status"] = "completed"
        result["data"] = scrape_result["result"]
        result["execution_info"] = scrape_result["execution_info"]
        
    except Exception as e:
        print("\nError occurred:")
        print(traceback.format_exc())
        result["status"] = "failed"
        result["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc()
        }
    finally:
        save_progress(result, start_time)

if __name__ == "__main__":
    main()
