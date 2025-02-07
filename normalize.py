from typing import List, Dict, Optional
from pathlib import Path
import json
from datetime import datetime
from dotenv import load_dotenv
import os
from database import MongoManager
from pydantic import BaseModel, Field
from models import Gun
from bson import ObjectId
from openai import OpenAI

# Configuration
NORMALIZE_ALL = False  # Set to True to normalize all listings
BATCH_SIZE = 20  # Process listings in batches (OpenAI allows up to 20 messages per request)
MODEL = "openai/gpt-4o-mini"  # Model to use for normalization

class GunNormalization(BaseModel):
    """Normalized gun information extracted from listing"""
    manufacturer: str = Field(description="Standardized manufacturer name")
    model: str = Field(description="Standardized model name")
    caliber: Optional[str] = Field(description="Standardized caliber")
    condition: Optional[str] = Field(description="Standardized condition")
    is_gun_listing: bool = Field(description="Whether this listing is definitely for a firearm")
    confidence: float = Field(description="Confidence score of the extraction (0-1)")
    original_text: str = Field(description="Original listing text that was analyzed")

def setup_openai():
    """Configure OpenAI client to use OpenRouter"""
    return OpenAI(
        api_key=os.getenv("OPENROUTER_KEY"),
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/zudsniper/gunscraper",
            "X-Title": "gunscraper"
        }
    )

def get_query(normalize_all: bool = False) -> Dict:
    """Get the appropriate MongoDB query based on normalization mode"""
    if normalize_all:
        return {}
    else:
        return {
            "$or": [
                {"guns": []},  # Empty guns array
                {"guns": None},  # No guns field
                {"guns": {"$exists": False}},  # Missing guns field
                {"guns": {"$size": 0}},  # Empty array
                {"normalized_at": {"$exists": False}}  # Never normalized
            ]
        }

def create_listing_messages(listings: List[Dict]) -> List[Dict]:
    """Create messages for batch processing"""
    messages = []
    for listing in listings:
        prompt = f"""Analyze this gun listing and extract standardized information.
        Focus on identifying the manufacturer, model, and caliber with proper capitalization.
        Common manufacturer examples: Smith & Wesson, Sig Sauer, Glock, Ruger, etc.
        
        Listing Title: {listing.get('title', '')}
        Description: {listing.get('description', '')}
        Current Gun Data: {json.dumps(listing.get('guns', []))}
        
        Rules:
        1. Manufacturer names should be properly capitalized (e.g., "Smith & Wesson" not "smith and wesson")
        2. Model names should follow manufacturer conventions (e.g., "M&P Shield" not "shield")
        3. Calibers should be standardized (e.g., ".45 ACP" not "45acp")
        4. If unsure about any field, use null
        5. Set is_gun_listing=true only if the listing is definitely for a firearm
        6. Provide a confidence score (0-1) for the extraction"""

        messages.append({
            "role": "user",
            "content": prompt
        })
    return messages

def normalize_listings_batch(client: OpenAI, listings: List[Dict]) -> List[Optional[GunNormalization]]:
    """Normalize a batch of listings using OpenAI"""
    try:
        messages = create_listing_messages(listings)
        responses = []

        # Create batch request
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a firearms expert who normalizes gun listing data."}
            ] + messages,
            response_format={
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "manufacturer": {
                            "type": "string",
                            "description": "Standardized manufacturer name (e.g., 'Smith & Wesson', 'Sig Sauer')"
                        },
                        "model": {
                            "type": "string",
                            "description": "Standardized model name following manufacturer conventions"
                        },
                        "caliber": {
                            "type": ["string", "null"],
                            "description": "Standardized caliber (e.g., '.45 ACP', '9mm') or null if unknown"
                        },
                        "condition": {
                            "type": ["string", "null"],
                            "description": "Standardized condition (e.g., 'New', 'Used') or null if unknown"
                        },
                        "is_gun_listing": {
                            "type": "boolean",
                            "description": "True if the listing is definitely for a firearm"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence score of the extraction"
                        }
                    },
                    "required": [
                        "manufacturer",
                        "model",
                        "caliber",
                        "condition",
                        "is_gun_listing",
                        "confidence"
                    ]
                }
            }
        )

        # Process responses
        for i, choice in enumerate(response.choices):
            if choice.message and choice.message.content:
                result = json.loads(choice.message.content)
                result["original_text"] = f"{listings[i].get('title', '')} {listings[i].get('description', '')}"
                responses.append(GunNormalization(**result))
            else:
                responses.append(None)

        return responses

    except Exception as e:
        print(f"Error processing batch: {str(e)}")
        return [None] * len(listings)

def update_listing_guns(db: MongoManager, listing_id: ObjectId, normalized: GunNormalization):
    """Update a listing with normalized gun data"""
    if not normalized.is_gun_listing:
        return
    
    gun = Gun(
        manufacturer=normalized.manufacturer,
        model=normalized.model,
        caliber=normalized.caliber if normalized.caliber else "NA",
        condition=normalized.condition if normalized.condition else "NA"
    )
    
    db.listings.update_one(
        {"_id": listing_id},
        {
            "$set": {
                "guns": [gun.dict()],
                "normalized_at": datetime.now().isoformat(),
                "normalization_confidence": normalized.confidence
            }
        }
    )

def process_batch(client: OpenAI, db: MongoManager, listings: List[Dict]):
    """Process a batch of listings"""
    print(f"\nProcessing batch of {len(listings)} listings")
    
    try:
        normalizations = normalize_listings_batch(client, listings)
        
        for listing, normalized in zip(listings, normalizations):
            if normalized:
                print(f"\nProcessing: {listing.get('title', 'No Title')}")
                print(f"Confidence: {normalized.confidence}")
                print(f"Is Gun: {normalized.is_gun_listing}")
                if normalized.is_gun_listing:
                    print(f"Manufacturer: {normalized.manufacturer}")
                    print(f"Model: {normalized.model}")
                    print(f"Caliber: {normalized.caliber}")
                    
                    update_listing_guns(db, listing["_id"], normalized)
                    print("Updated listing in database")
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving progress...")
        return False
    except Exception as e:
        print(f"Error processing batch: {str(e)}")
    
    return True

def main():
    load_dotenv()
    client = setup_openai()
    
    # Initialize MongoDB connection
    db = MongoManager()
    
    try:
        # Get appropriate query based on NORMALIZE_ALL setting
        query = get_query(NORMALIZE_ALL)
        
        total_listings = db.listings.count_documents(query)
        print(f"Found {total_listings} listings to normalize")
        
        # Process listings in batches
        for skip in range(0, total_listings, BATCH_SIZE):
            print(f"\nProcessing batch {skip//BATCH_SIZE + 1}/{(total_listings + BATCH_SIZE - 1)//BATCH_SIZE}")
            
            batch = list(db.listings.find(query).skip(skip).limit(BATCH_SIZE))
            if not process_batch(client, db, batch):
                break
        
        print("\nNormalization complete!")
        
    except Exception as e:
        print(f"Error during normalization: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main() 