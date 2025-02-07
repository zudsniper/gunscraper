from pathlib import Path
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from scrapegraphai.graphs import SearchGraph
from scrapegraphai.utils import prettify_exec_info
import os
from datetime import datetime
from statistics import mean, median
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
import hashlib

class GunListing(BaseModel):
    """Individual gun listing from a dealer/marketplace"""
    dealer: str = Field(description="Name of the dealer or marketplace")
    price: float = Field(description="Price of the firearm")
    condition: str = Field(description="Condition of the firearm (new, used, etc)")
    url: str = Field(description="URL to the listing")
    date_found: str = Field(description="Date the listing was found")
    in_stock: bool = Field(description="Whether the item is in stock")

class GunPriceSearch(BaseModel):
    """Collection of prices for a specific firearm model"""
    manufacturer: str = Field(description="Manufacturer of the firearm")
    model: str = Field(description="Model of the firearm")
    caliber: Optional[str] = Field(description="Caliber of the firearm if specified")
    listings: List[GunListing] = Field(description="List of found listings")
    last_updated: str = Field(description="When this price data was last updated")
    gun_hash: str = Field(description="Unique identifier for this gun model")

    @property
    def average_price(self) -> float:
        """Calculate average price from in-stock listings"""
        prices = [l.price for l in self.listings if l.in_stock and l.price > 0]
        return mean(prices) if prices else 0

    @property
    def median_price(self) -> float:
        """Calculate median price from in-stock listings"""
        prices = [l.price for l in self.listings if l.in_stock and l.price > 0]
        return median(prices) if prices else 0

class MongoManager:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
        self.db: Database = self.client.gun_market_data
        self.scraped_listings: Collection = self.db.scraped_listings
        self.market_prices: Collection = self.db.market_prices
        self.price_analyses: Collection = self.db.price_analyses
        
        # Create indexes
        self.market_prices.create_index("gun_hash", unique=True)
        self.scraped_listings.create_index("listing_url", unique=True)
        self.price_analyses.create_index([
            ("gun_hash", 1),
            ("listing_url", 1)
        ], unique=True)

    def generate_gun_hash(self, manufacturer: str, model: str, caliber: Optional[str] = None) -> str:
        """Generate a unique hash for a gun model"""
        # Normalize strings
        manufacturer = manufacturer.lower().strip()
        model = model.lower().strip()
        caliber = caliber.lower().strip() if caliber and caliber != "NA" else ""
        
        # Create hash
        hash_string = f"{manufacturer}|{model}|{caliber}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def save_scraped_listings(self, listings_data: dict):
        """Save scraped listings to MongoDB"""
        for page in listings_data["data"]["pages"]:
            if not page.get("listing_previews"):
                continue
                
            for listing in page["listing_previews"]["listings"]:
                listing["_id"] = listing["listing_url"]  # Use listing URL as unique ID
                self.scraped_listings.update_one(
                    {"_id": listing["_id"]},
                    {"$set": listing},
                    upsert=True
                )

    def get_market_price(self, gun_hash: str) -> Optional[dict]:
        """Get existing market price data if not too old"""
        price_data = self.market_prices.find_one({"gun_hash": gun_hash})
        if price_data:
            last_updated = datetime.fromisoformat(price_data["last_updated"])
            if (datetime.now() - last_updated).days < 7:  # Cache for 7 days
                return price_data
        return None

def create_search_prompt(gun) -> str:
    """Create a search prompt for a specific gun"""
    prompt = f"""
    Find current market prices for the {gun['manufacturer']} {gun['model']} firearm
    {f"in {gun['caliber']}" if gun['caliber'] and gun['caliber'] != 'NA' else ''}.
    
    Search multiple dealers including:
    - GunBroker
    - Guns.com
    - Primary Arms
    - Palmetto State Armory
    - Local gun shops
    
    For each listing found, include:
    - Exact dealer name
    - Current price
    - Condition (new/used)
    - Whether it's in stock
    - URL to listing
    """
    return prompt

def search_market_price(gun: dict, config: dict, db: MongoManager) -> GunPriceSearch:
    """Search for market prices of a specific gun"""
    gun_hash = db.generate_gun_hash(gun["manufacturer"], gun["model"], gun["caliber"])
    
    # Check cache first
    cached_data = db.get_market_price(gun_hash)
    if cached_data:
        return GunPriceSearch(**cached_data)
    
    # If no cache, perform search
    search_graph = SearchGraph(
        prompt=create_search_prompt(gun),
        config=config,
        schema=GunPriceSearch
    )
    
    result = search_graph.run()
    result.gun_hash = gun_hash
    result.last_updated = datetime.now().isoformat()
    
    # Save to database
    db.market_prices.update_one(
        {"gun_hash": gun_hash},
        {"$set": result.dict()},
        upsert=True
    )
    
    return result

def analyze_listing_price(listing_price: float, market_data: GunPriceSearch) -> dict:
    """Analyze how a listing price compares to market prices"""
    if market_data.average_price == 0:
        return {"status": "no_data", "message": "No market data available"}
    
    price_diff = listing_price - market_data.median_price
    price_diff_pct = (price_diff / market_data.median_price) * 100
    
    return {
        "listing_price": listing_price,
        "market_median": market_data.median_price,
        "market_average": market_data.average_price,
        "price_difference": price_diff,
        "price_difference_percent": price_diff_pct,
        "status": "overpriced" if price_diff_pct > 10 else "underpriced" if price_diff_pct < -10 else "fair_price"
    }

def main():
    load_dotenv()
    
    # Configure the search graph
    graph_config = {
        "llm": {
            "api_key": os.getenv("OPENROUTER_KEY"),
            "model": "openai/gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
        },
        "max_results": 5,
        "verbose": True,
    }
    
    # Initialize MongoDB connection
    db = MongoManager()
    
    # Load and save scraped listings
    with open("scraping_results.json", 'r') as f:
        data = json.load(f)
    db.save_scraped_listings(data)
    
    # Process each listing with guns
    for listing in db.scraped_listings.find():
        if not listing.get("guns"):
            continue
            
        for gun in listing["guns"]:
            if gun["manufacturer"] == "NA" or gun["model"] == "NA":
                continue
                
            print(f"\nAnalyzing: {gun['manufacturer']} {gun['model']}")
            
            try:
                # Get or fetch market data
                market_data = search_market_price(gun, graph_config, db)
                analysis = analyze_listing_price(listing["price"], market_data)
                
                # Save analysis
                analysis_doc = {
                    "gun_hash": market_data.gun_hash,
                    "listing_url": listing["listing_url"],
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat()
                }
                
                db.price_analyses.update_one(
                    {
                        "gun_hash": market_data.gun_hash,
                        "listing_url": listing["listing_url"]
                    },
                    {"$set": analysis_doc},
                    upsert=True
                )
                
                print(f"Status: {analysis['status']}")
                print(f"Market median: ${analysis['market_median']:,.2f}")
                print(f"Listing price: ${analysis['listing_price']:,.2f}")
                print(f"Difference: {analysis['price_difference_percent']:.1f}%")
                
            except Exception as e:
                print(f"Error processing {gun['manufacturer']} {gun['model']}: {str(e)}")

if __name__ == "__main__":
    main()
