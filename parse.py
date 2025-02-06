from pathlib import Path
import json
from collections import Counter, defaultdict
from statistics import mean, median, stdev
from typing import List, Dict
from models import ListingsPages, ListingPreview
from pprint import pprint

def load_scraped_data(file_path: Path = Path("scraping_results.json")) -> ListingsPages:
    """Load the scraped data from JSON file"""
    with open(file_path, 'r') as f:
        data = json.load(f)
        return ListingsPages(**data["data"])

def calculate_price_stats(listings: List[ListingPreview]) -> Dict:
    """Calculate price statistics"""
    # Filter out $0 prices which are likely "make offer"
    prices = [l.price for l in listings if l.price > 0]
    
    return {
        "count": len(prices),
        "mean": round(mean(prices), 2),
        "median": round(median(prices), 2),
        "std_dev": round(stdev(prices), 2),
        "min": min(prices),
        "max": max(prices),
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
        "total_listings": len(listings),
        "listings_with_guns": len([l for l in listings if l.guns]),
        "guns_per_listing": dict(guns_per_listing.most_common()),
        "images_per_listing": dict(images_per_listing.most_common())
    }

def main():
    # Load data
    data = load_scraped_data()
    listings = data.all_listings
    
    # Calculate statistics
    stats = {
        "price_stats": calculate_price_stats(listings),
        "gun_stats": analyze_guns(listings),
        "listing_stats": analyze_listings(listings)
    }
    
    # Print results
    print("\n=== Price Statistics ===")
    print(f"Number of priced listings: {stats['price_stats']['count']}")
    print(f"Average price: ${stats['price_stats']['mean']:,.2f}")
    print(f"Median price: ${stats['price_stats']['median']:,.2f}")
    print(f"Price range: ${stats['price_stats']['min']:,.2f} - ${stats['price_stats']['max']:,.2f}")
    print("\nPrice Distribution:")
    for range_name, count in stats['price_stats']['price_ranges'].items():
        print(f"${range_name}: {count} listings")
    
    print("\n=== Gun Statistics ===")
    print("\nTop 10 Manufacturers:")
    for mfg, count in stats['gun_stats']['top_manufacturers'].items():
        print(f"{mfg}: {count}")
    
    print("\nTop 10 Models:")
    for model, count in stats['gun_stats']['top_models'].items():
        print(f"{model}: {count}")
    
    print("\nTop Calibers:")
    for caliber, count in stats['gun_stats']['top_calibers'].items():
        print(f"{caliber}: {count}")
    
    print("\n=== Listing Statistics ===")
    print(f"Total listings: {stats['listing_stats']['total_listings']}")
    print(f"Listings with guns: {stats['listing_stats']['listings_with_guns']}")
    
    print("\nGuns per listing:")
    for num_guns, count in stats['listing_stats']['guns_per_listing'].items():
        print(f"{num_guns} gun(s): {count} listings")
    
    # Save detailed stats to file
    output_file = Path("listing_analysis.json")
    with open(output_file, 'w') as f:
        json.dump(stats, f, indent=4)
    print(f"\nDetailed statistics saved to {output_file}")

if __name__ == "__main__":
    main()
