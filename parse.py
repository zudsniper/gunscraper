from pathlib import Path
import json
from collections import Counter, defaultdict
from statistics import mean, median, stdev
from typing import List, Dict
from models import ListingsPages, ListingPreview
from pprint import pprint
from datetime import datetime
from dotenv import load_dotenv
import os
from database import MongoManager

def load_scraped_data(file_path: Path = Path("scraping_results.json")) -> tuple[ListingsPages, dict]:
    """Load the scraped data from JSON file"""
    with open(file_path, 'r') as f:
        data = json.load(f)
        return ListingsPages(**data["data"]), data

def calculate_price_stats(listings: List[ListingPreview]) -> Dict:
    """Calculate price statistics"""
    # Filter out $0 prices which are likely "make offer"
    prices = [l.price for l in listings if l.price > 0]
    
    return {
        "type": "price_stats",
        "count": len(prices),
        "mean": round(mean(prices), 2),
        "median": round(median(prices), 2),
        "std_dev": round(stdev(prices), 2) if len(prices) > 1 else 0,
        "min": min(prices) if prices else 0,
        "max": max(prices) if prices else 0,
        "price_ranges": {
            "0-500": len([p for p in prices if p <= 500]),
            "501-1000": len([p for p in prices if 500 < p <= 1000]),
            "1001-2000": len([p for p in prices if 1000 < p <= 2000]),
            "2001+": len([p for p in prices if p > 2000])
        }
    }

def analyze_guns(listings: List[ListingPreview]) -> Dict:
    """Analyze gun-related statistics"""
    manufacturers = Counter()
    models = Counter()
    calibers = Counter()
    conditions = Counter()
    
    for listing in listings:
        if listing.guns:
            for gun in listing.guns:
                if gun.manufacturer != "NA":
                    manufacturers[gun.manufacturer] += 1
                if gun.model != "NA":
                    models[gun.model] += 1
                if gun.caliber != "NA":
                    calibers[gun.caliber] += 1
                if gun.condition and gun.condition != "NA":
                    conditions[gun.condition] += 1
    
    return {
        "type": "gun_stats",
        "top_manufacturers": dict(manufacturers.most_common(10)),
        "top_models": dict(models.most_common(10)),
        "top_calibers": dict(calibers.most_common(10)),
        "conditions": dict(conditions.most_common())
    }

def analyze_listings(listings: List[ListingPreview]) -> Dict:
    """Analyze listing patterns"""
    guns_per_listing = Counter(len(listing.guns) if listing.guns else 0 for listing in listings)
    images_per_listing = Counter(len(listing.image_urls) for listing in listings)
    
    return {
        "type": "listing_stats",
        "total_listings": len(listings),
        "listings_with_guns": len([l for l in listings if l.guns]),
        "guns_per_listing": {str(k): v for k, v in guns_per_listing.most_common()},
        "images_per_listing": {str(k): v for k, v in images_per_listing.most_common()}
    }

def print_analysis_results(price_stats: Dict, gun_stats: Dict, listing_stats: Dict):
    """Print analysis results in a readable format"""
    print("\n=== Price Statistics ===")
    print(f"Number of priced listings: {price_stats['count']}")
    print(f"Average price: ${price_stats['mean']:,.2f}")
    print(f"Median price: ${price_stats['median']:,.2f}")
    print(f"Price range: ${price_stats['min']:,.2f} - ${price_stats['max']:,.2f}")
    
    print("\nPrice Distribution:")
    for range_name, count in price_stats['price_ranges'].items():
        print(f"${range_name}: {count} listings")
    
    print("\n=== Gun Statistics ===")
    print("\nTop 10 Manufacturers:")
    for mfg, count in gun_stats['top_manufacturers'].items():
        print(f"{mfg}: {count}")
    
    print("\nTop 10 Models:")
    for model, count in gun_stats['top_models'].items():
        print(f"{model}: {count}")
    
    print("\nTop Calibers:")
    for caliber, count in gun_stats['top_calibers'].items():
        print(f"{caliber}: {count}")
    
    print("\n=== Listing Statistics ===")
    print(f"Total listings: {listing_stats['total_listings']}")
    print(f"Listings with guns: {listing_stats['listings_with_guns']}")
    
    print("\nGuns per listing:")
    for num_guns_str, count in sorted(listing_stats['guns_per_listing'].items(), 
                                    key=lambda x: int(x[0])):
        print(f"{num_guns_str} gun(s): {count} listings")

def main():
    # Load environment variables
    load_dotenv()
    
    try:
        # Initialize MongoDB connection
        db = MongoManager()
        
        # Load and process data
        listings_pages, raw_data = load_scraped_data()
        listings = listings_pages.all_listings
        
        # Save scraping session and get session ID
        session_id = db.save_scraping_session(raw_data)
        print(f"\nCreated new scraping session: {session_id}")
        
        # Save listings
        db.save_listings(session_id, listings)
        print(f"Saved {len(listings)} listings to database")
        
        # Calculate statistics
        price_stats = calculate_price_stats(listings)
        gun_stats = analyze_guns(listings)
        listing_stats = analyze_listings(listings)
        
        # Save statistics
        for stats in [price_stats, gun_stats, listing_stats]:
            db.save_statistics(session_id, stats)
        
        # Print analysis results
        print_analysis_results(price_stats, gun_stats, listing_stats)
        
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        raise
    finally:
        # Ensure database connection is closed
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    main()
  