from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class Condition(str, Enum):
    NEW = "new"
    LIKE_NEW = "like new"
    USED = "used"
    ROUNDS_FIRED = "rounds_fired"
    NA = "NA"  # Added for cases where condition is not specified

class ItemType(str, Enum):
    GUN = "gun"
    MAGAZINE = "magazine"
    AMMUNITION = "ammunition"
    OPTIC = "optic"
    LIGHT = "light"
    HOLSTER = "holster"
    BODY_ARMOR = "body_armor"
    OTHER = "other"

class Gun(BaseModel):
    manufacturer: str
    model: str
    caliber: str
    condition: Condition
    description: Optional[str] = None
    color: Optional[str] = None
    
    # Basic specs
    barrel_length: Optional[str] = None
    capacity: Optional[int] = None
    
    # Accessories
    optic: Optional[str] = None
    light: Optional[str] = None
    modifications: Optional[List[str]] = None

class Magazine(BaseModel):
    manufacturer: str
    compatibility: str  # What gun it fits
    capacity: int
    caliber: str

class Ammunition(BaseModel):
    manufacturer: str
    caliber: str
    quantity: int
    grain: Optional[int] = None

class OtherItem(BaseModel):
    item_type: ItemType
    manufacturer: str
    model: Optional[str] = None
    description: str
    condition: Optional[Condition] = None

class Status(str, Enum):
    AVAILABLE = "available"
    SOLD = "sold"

class Listing(BaseModel):
    title: str = Field(description="The title of the listing")
    price: float = Field(description="The total price of the listing")
    location: str = Field(description="Location of the listing")
    description: str = Field(description="The full description from the listing")
    status: Status = Field(default=Status.AVAILABLE, description="Current status of the listing")
    
    # Items in listing
    guns: List[Gun] = Field(default_factory=list)
    magazines: List[Magazine] = Field(default_factory=list)
    ammunition: List[Ammunition] = Field(default_factory=list)
    other_items: List[OtherItem] = Field(default_factory=list)
    
    # Listing metadata
    image_urls: List[str] = Field(default_factory=list)
    listing_url: str = Field(description="URL of the listing")
    listing_age_days: Optional[float] = Field(description="Age of listing in days")
    seller_info: Optional[str] = None

class Listings(BaseModel):
    listings: List[Listing] = Field(description="List of all listings found on the page")

class GunPreview(BaseModel):
    manufacturer: str
    model: str
    caliber: str
    condition: Optional[Condition] = None

class ListingPreview(BaseModel):
    title: str = Field(description="The title of the listing")
    price: float = Field(description="The total price of the listing")
    description: str = Field(description="The full description from the listing")
    
    # Preview items (simplified)
    guns: Optional[List[GunPreview]] = Field(default=None)
    listing_url: str = Field(description="URL of the detailed listing")
    image_urls: List[str] = Field(default_factory=list)

class ListingPreviews(BaseModel):
    listings: List[ListingPreview] = Field(description="List of all listing previews found on the page")

class ListingsPage(BaseModel):
    page_url: str = Field(description="URL of the page")
    page_number: int = Field(description="Page number of the page")
    listing_previews: Optional[ListingPreviews] = Field(default=None, description="List of all listing previews found on the page")

class ListingsPages(BaseModel):
    pages: List[ListingsPage] = Field(description="List of all pages found")
    num_pages: Optional[int] = Field(default=None, description="Number of pages found total")

    @property
    def all_listings(self) -> List[ListingPreview]:
        """Get all listing previews from all pages in a single flat list"""
        return [
            preview 
            for page in self.pages 
            if page.listing_previews 
            for preview in page.listing_previews.listings
        ]
