import os
from pathlib import Path
import json
from dotenv import load_dotenv
from scrapegraphai.graphs import SmartScraperGraph
from scrapegraphai.utils import prettify_exec_info
from scrapegraphai.models.oneapi import OneApi
from models import ListingPreviews, ListingsPages, ListingsPage
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from datetime import datetime
import traceback

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

def run_scraper(url: str, result: dict, start_time: datetime) -> dict:
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

    graph_config = {
        "llm": {
            "api_key": os.getenv("OPENROUTER_KEY"),
            "model": "openai/gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
        },
        "verbose": True,
        "headless": False,
    }
    
    listing_page_prompt = """
    Extract all listings from this page. 
    For each listing, extract the following:
    - title
    - price
    - description: a description of the listing 
    - guns: all the firearms listed
      - manufacturer
      - model 
      - caliber 
      - condition: new, like new, used
    - image_urls: Capture all image URLs 
    - listing_url: the URL of the detailed listing
    """

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
        
        smart_scraper_graph = SmartScraperGraph(
            prompt=listing_page_prompt,
            source=page_url,
            config=graph_config,
            schema=ListingPreviews,
        )

        listing_previews = smart_scraper_graph.run()
        execution_info.append(smart_scraper_graph.get_execution_info())
        
        new_page = ListingsPage(
            page_url=page_url,
            page_number=page_num,
            listing_previews=listing_previews
        )
        pages.pages.append(new_page)
        
        # # Print the data as we get it
        # print("\nNew listings found:")
        # for listing in listing_previews.listings:
        #     print(f"\nTitle: {listing.title}")
        #     print(f"Price: {listing.price}")
        #     for gun in listing.guns:
        #         print(f"Gun: {gun.manufacturer} {gun.model} ({gun.caliber})")
        
        # Update result data and save progress
        result["data"] = pages.model_dump()
        result["last_completed_page"] = page_num
        save_progress(result, start_time)
        
        print(execution_info[-1])
        print('done, next page...')

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
    
    try:
        print(f"Processing URL: {url}")
        scrape_result = run_scraper(url, result, start_time)
        
        result["status"] = "completed"
        result["data"] = scrape_result["result"]  # This now contains the actual data
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
