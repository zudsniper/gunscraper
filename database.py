from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from datetime import datetime
from typing import Optional, Dict, List
import hashlib
import os
from models import ItemType, ListingPreview, ItemPreview

class MongoManager:
    """Unified MongoDB manager for marketplace data"""
    
    def __init__(self):
        # Load MongoDB configuration from environment
        self.client = MongoClient(
            host=os.getenv("MONGODB_HOST", "localhost"),
            port=int(os.getenv("MONGODB_PORT", 27017)),
            username=os.getenv("MONGODB_USERNAME"),
            password=os.getenv("MONGODB_PASSWORD"),
            authSource=os.getenv("MONGODB_AUTH_DB", "admin")
        )
        self.db_name = os.getenv("MONGODB_DB_NAME", "gun_market_data")
        self.db: Database = self.client[self.db_name]
        
        # Collections
        self.scraping_sessions: Collection = self.db.scraping_sessions
        self.listings: Collection = self.db.listings
        self.statistics: Collection = self.db.statistics
        self.market_prices: Collection = self.db.market_prices
        self.price_analyses: Collection = self.db.price_analyses
        
        # Setup indexes
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Setup necessary database indexes"""
        # Scraping sessions indexes
        self.scraping_sessions.create_index([
            ("root_url", ASCENDING),
            ("start_time", DESCENDING)
        ])
        
        # Listings indexes
        self.listings.create_index([
            ("session_id", ASCENDING),
            ("listing_url", ASCENDING)
        ], unique=True)
        self.listings.create_index("items.manufacturer")
        self.listings.create_index("items.model")
        self.listings.create_index("items.item_type")
        self.listings.create_index("price")
        
        # Market prices indexes
        self.market_prices.create_index([
            ("item_hash", ASCENDING),
            ("item_type", ASCENDING)
        ], unique=True)
        self.market_prices.create_index("last_updated")
        
        # Price analyses indexes
        self.price_analyses.create_index([
            ("item_hash", ASCENDING),
            ("item_type", ASCENDING),
            ("listing_url", ASCENDING)
        ], unique=True)
        
        # Statistics indexes
        self.statistics.create_index([
            ("session_id", ASCENDING),
            ("type", ASCENDING)
        ])

    def generate_item_hash(self, item: ItemPreview) -> str:
        """Generate a unique hash for an item"""
        # Normalize strings
        manufacturer = item.manufacturer.lower().strip() if item.manufacturer else ""
        model = item.model.lower().strip() if item.model else ""
        
        # Add type-specific fields to hash
        extra_fields = []
        if item.item_type == ItemType.GUN:
            caliber = item.caliber.lower().strip() if item.caliber else ""
            extra_fields.append(caliber)
        elif item.item_type == ItemType.MAGAZINE:
            caliber = item.caliber.lower().strip() if item.caliber else ""
            capacity = str(item.capacity) if item.capacity else ""
            extra_fields.extend([caliber, capacity])
        elif item.item_type == ItemType.AMMUNITION:
            caliber = item.caliber.lower().strip() if item.caliber else ""
            extra_fields.append(caliber)
        
        # Create hash
        hash_string = f"{item.item_type}|{manufacturer}|{model}|{'|'.join(extra_fields)}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def save_scraping_session(self, data: dict) -> str:
        """Save a new scraping session and return its ID"""
        session = {
            "root_url": data["url"],
            "start_time": datetime.fromisoformat(data["start_time"]),
            "end_time": datetime.fromisoformat(data["end_time"]),
            "status": data["status"],
            "num_pages": data["data"]["num_pages"],
            "execution_info": data["execution_info"]
        }
        
        return str(self.scraping_sessions.insert_one(session).inserted_id)

    def save_listings(self, session_id: str, listings: List[ListingPreview]):
        """Save listings from a scraping session"""
        for listing in listings:
            listing_dict = listing.model_dump()
            listing_dict["session_id"] = session_id
            
            # Generate hashes for all items
            for item in listing_dict["items"]:
                item["item_hash"] = self.generate_item_hash(ItemPreview(**item))
            
            self.listings.update_one(
                {
                    "session_id": session_id,
                    "listing_url": listing_dict["listing_url"]
                },
                {"$set": listing_dict},
                upsert=True
            )

    def _ensure_string_keys(self, data: Dict) -> Dict:
        """Recursively convert all dictionary keys to strings"""
        if not isinstance(data, dict):
            return data
        
        return {
            str(key): self._ensure_string_keys(value) if isinstance(value, dict) else value
            for key, value in data.items()
        }

    def save_statistics(self, session_id: str, stats: Dict):
        """Save analysis statistics for a session"""
        stats["session_id"] = session_id
        stats["calculated_at"] = datetime.now()
        # Convert all keys to strings before saving
        stats = self._ensure_string_keys(stats)
        self.statistics.insert_one(stats)

    def get_market_price(self, item_hash: str, item_type: ItemType, max_age_days: int = 7) -> Optional[dict]:
        """Get existing market price data if not too old"""
        price_data = self.market_prices.find_one({
            "item_hash": item_hash,
            "item_type": item_type
        })
        if price_data:
            last_updated = datetime.fromisoformat(price_data["last_updated"])
            if (datetime.now() - last_updated).days < max_age_days:
                return price_data
        return None

    def save_market_price(self, price_data: dict):
        """Save or update market price data"""
        self.market_prices.update_one(
            {
                "item_hash": price_data["item_hash"],
                "item_type": price_data["item_type"]
            },
            {"$set": price_data},
            upsert=True
        )

    def save_price_analysis(self, analysis: dict):
        """Save price analysis results"""
        self.price_analyses.update_one(
            {
                "item_hash": analysis["item_hash"],
                "item_type": analysis["item_type"],
                "listing_url": analysis["listing_url"]
            },
            {"$set": analysis},
            upsert=True
        )

    def get_session_listings(self, session_id: str):
        """Get all listings for a specific session"""
        return self.listings.find({"session_id": session_id})

    def get_latest_session(self, root_url: Optional[str] = None):
        """Get the most recent scraping session, optionally filtered by URL"""
        query = {"root_url": root_url} if root_url else {}
        return self.scraping_sessions.find_one(
            query,
            sort=[("start_time", DESCENDING)]
        )

    def get_item_analyses(self, item_hash: str, item_type: ItemType):
        """Get all price analyses for a specific item"""
        return self.price_analyses.find({
            "item_hash": item_hash,
            "item_type": item_type
        })

    def close(self):
        """Close the MongoDB connection"""
        self.client.close() 