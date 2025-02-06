from pydantic import BaseModel, Field
from typing import List, Optional, Union, Set
from enum import Enum

# Base enums from previous file
class Condition(str, Enum):
    NEW = "new"
    LIKE_NEW = "like new"
    USED = "used"
    ROUNDS_FIRED = "rounds_fired"

class AmmoJacketing(str, Enum):
    FMJ = "FMJ"
    JHP = "JHP"
    SP = "SP"
    TMJ = "TMJ"
    FRANGIBLE = "Frangible"

class ArmorLevel(str, Enum):
    LEVEL_2 = "Level II"
    LEVEL_3 = "Level III"
    LEVEL_3A = "Level IIIA"
    LEVEL_3_PLUS = "Level III+"
    LEVEL_4 = "Level IV"

# New enums for parts
class PlatformFamily(str, Enum):
    AR15 = "AR-15"
    AR10 = "AR-10"
    AK47 = "AK-47"
    G17 = "Glock 17 size"  # Full size 9mm (G17, P320 Full, M&P 2.0 Full)
    G19 = "Glock 19 size"  # Compact 9mm (G19, P320 Compact, MR920, M&P 2.0 Compact)
    G26 = "Glock 26 size"  # Subcompact 9mm
    G43 = "Glock 43 size"  # Single stack/micro 9mm (G43, P365, Shield)
    G20 = "Glock 20 size"  # Full size 10mm
    G21 = "Glock 21 size"  # Full size .45
    G30 = "Glock 30 size"  # Compact .45
    P320_FCU = "P320 FCU"  # Sig P320 Fire Control Unit platform
    P365_FCU = "P365 FCU"  # Sig P365 Fire Control Unit platform
    OTHER = "other"

class PartCategory(str, Enum):
    IRON_SIGHT = "iron_sight"
    OPTIC = "optic"
    STOCK = "stock"
    HANDGUARD = "handguard"
    GRIP = "grip"
    TRIGGER = "trigger"
    BARREL = "barrel"
    BOLT_CARRIER_GROUP = "bcg"
    CHARGING_HANDLE = "charging_handle"
    MUZZLE_DEVICE = "muzzle_device"
    FOREGRIP = "foregrip"
    PISTOL_GRIP = "pistol_grip"
    LIGHT = "light"
    UPPER_RECEIVER = "upper_receiver"
    LOWER_RECEIVER = "lower_receiver"
    OTHER = "other"

class SightType(str, Enum):
    FIXED = "fixed"
    ADJUSTABLE = "adjustable"
    NIGHT_SIGHT = "night_sight"
    FIBER_OPTIC = "fiber_optic"
    TRITIUM = "tritium"

class OpticType(str, Enum):
    RED_DOT = "red_dot"
    HOLOGRAPHIC = "holographic"
    PRISM = "prism"
    LPVO = "lpvo"
    SCOPE = "scope"

# Base class for parts
class BasePart(BaseModel):
    manufacturer: str
    model: str
    condition: Union[Condition, str]
    description: Optional[str] = None
    platform_family: Optional[PlatformFamily] = None
    specific_model_compatibility: Optional[List[str]] = None  # e.g., ["Glock 19", "Glock 17"]
    
    class Config:
        extra = "allow"

class Sight(BasePart):
    sight_type: SightType
    color: Optional[str] = None
    illumination: Optional[str] = None  # e.g., "green tritium"
    adjustable: bool = False
    
class Optic(BasePart):
    optic_type: OpticType
    magnification: Optional[Union[float, str]] = None  # Could be "1x" or "1-6x" or 1.0
    reticle: Optional[str] = None
    illuminated: bool = False
    battery_type: Optional[str] = None
    mount_type: Optional[str] = None  # e.g., "Picatinny"

class Stock(BasePart):
    adjustable: bool = False
    material: Optional[str] = None
    color: Optional[str] = None
    buffer_tube_compatibility: Optional[str] = None  # e.g., "mil-spec", "commercial"

class Handguard(BasePart):
    length: str  # e.g., "15 inch"
    material: str
    mounting_system: str  # e.g., "M-LOK", "KeyMod", "Picatinny"
    weight: Optional[float] = None  # in ounces
    color: Optional[str] = None

class MuzzleDeviceType(str, Enum):
    SUPPRESSOR = "suppressor"
    COMPENSATOR = "compensator"
    FLASH_HIDER = "flash_hider"
    BRAKE = "brake"
    OTHER = "other"

class Barrel(BasePart):
    length: str  # e.g., "16 inch"
    caliber: str
    twist_rate: Optional[str] = None  # e.g., "1:7"
    material: Optional[str] = None
    threaded: bool = False
    thread_pitch: Optional[str] = None  # e.g., "1/2x28"
    profile: Optional[str] = None  # e.g., "HBAR", "Government"
    
class Foregrip(BasePart):
    style: str  # e.g., "vertical", "angled"
    material: Optional[str] = None
    color: Optional[str] = None
    mounting_type: str  # e.g., "M-LOK", "Picatinny"

class PistolGrip(BasePart):
    material: Optional[str] = None
    color: Optional[str] = None
    angle: Optional[float] = None  # Grip angle in degrees
    texture: Optional[str] = None  # e.g., "aggressive", "smooth"
    storage: bool = False  # Whether grip has internal storage

class Light(BasePart):
    lumens: int
    battery_type: str
    mounting_type: str  # e.g., "M-LOK", "Picatinny"
    pressure_switch: bool = False
    runtime: Optional[str] = None  # e.g., "1.5 hours"
    waterproof_rating: Optional[str] = None  # e.g., "IPX7"

class MuzzleDevice(BasePart):
    device_type: MuzzleDeviceType
    caliber: str
    thread_pitch: str  # e.g., "1/2x28"
    length: Optional[str] = None
    diameter: Optional[str] = None
    weight: Optional[float] = None  # in ounces
    qd_mount: Optional[bool] = None  # Quick detach capability
    
    # Suppressor specific
    db_reduction: Optional[float] = None
    full_auto_rated: Optional[bool] = None
    
    # Compensator/brake specific
    ports: Optional[int] = None
    material: Optional[str] = None

class ARUpperReceiver(BasePart):
    assembled: bool = True  # Whether it's a complete upper or stripped
    caliber: Optional[str] = None  # Only if assembled
    barrel_length: Optional[str] = None  # Only if assembled
    handguard: Optional[Handguard] = None
    barrel: Optional[Barrel] = None
    bcg_included: bool = False
    charging_handle_included: bool = False
    forward_assist: bool = True
    dust_cover: bool = True
    material: Optional[str] = None  # e.g., "7075-T6 aluminum"
    finish: Optional[str] = None  # e.g., "anodized"
    feed_ramps: Optional[str] = None  # e.g., "M4"
    muzzle_device: Optional[MuzzleDevice] = None
    optics: Optional[List[Optic]] = Field(default_factory=list)
    sights: Optional[List[Sight]] = Field(default_factory=list)

class LowerReceiverType(str, Enum):
    STRIPPED = "stripped"
    COMPLETE = "complete"
    PISTOL = "pistol"
    RIFLE = "rifle"
    SBR = "sbr"  # Short Barrel Rifle

class ARLowerReceiver(BasePart):
    receiver_type: LowerReceiverType
    material: Optional[str] = None  # e.g., "7075-T6 aluminum"
    finish: Optional[str] = None  # e.g., "anodized"
    fire_control_group: Optional[str] = None  # e.g., "semi-auto only"
    trigger_installed: bool = False
    trigger_type: Optional[str] = None
    buffer_tube_type: Optional[str] = None  # e.g., "mil-spec", "commercial"
    stock: Optional[Stock] = None
    pistol_grip: Optional[PistolGrip] = None
    serial_number: Optional[str] = None  # If transferable/serialized
    
    # Additional features
    ambidextrous: bool = False
    enhanced_bolt_catch: bool = False
    enhanced_mag_release: bool = False
    integrated_trigger_guard: bool = True

class Gun(BaseModel):
    manufacturer: str
    model: str
    generation: Optional[str] = None
    caliber: str
    year: Optional[int] = None
    condition: Union[Condition, int]
    color: str
    platform_family: Optional[PlatformFamily] = None
    
    # Installed parts
    upper_receiver: Optional[ARUpperReceiver] = None
    lower_receiver: Optional[ARLowerReceiver] = None
    sights: Optional[List[Sight]] = Field(default_factory=list)
    optics: Optional[List[Optic]] = Field(default_factory=list)
    stock: Optional[Stock] = None
    handguard: Optional[Handguard] = None
    barrel: Optional[Barrel] = None
    foregrip: Optional[Foregrip] = None
    pistol_grip: Optional[PistolGrip] = None
    light: Optional[Light] = None
    muzzle_device: Optional[MuzzleDevice] = None
    
    # Additional installed parts can be added here
    additional_parts: Optional[List[BasePart]] = Field(default_factory=list)

# Previous models with minor updates
class Magazine(BaseModel):
    manufacturer: str
    compatibility: Union[str, PlatformFamily]  # Can be specific model or platform family
    capacity: int
    caliber: str

class Ammunition(BaseModel):
    quantity: int
    manufacturer: str
    jacketing: AmmoJacketing
    caliber: str
    grain: int

class OtherItemType(str, Enum):
    HOLSTER = "holster"
    BODY_ARMOR = "body_armor"
    OPTIC = "optic"
    LIGHT = "light"
    SLING = "sling"
    OTHER = "other"

class OtherItem(BaseModel):
    item_type: OtherItemType
    manufacturer: str
    model: Optional[str] = None
    compatible_with: Optional[Union[str, PlatformFamily]] = None
    armor_level: Optional[ArmorLevel] = None
    plate_size: Optional[str] = None
    description: str
    condition: Optional[Union[Condition, str]] = None

class PriceHistory(BaseModel):
    price: float
    date: str

class Listing(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    price_history: Optional[List[PriceHistory]] = Field(default_factory=list)
    
    # Location info
    location: str  # e.g., "Austin"
    
    # Timing info
    date_posted: str
    date_first_seen: str
    date_last_seen: str
    listing_age_days: Optional[float] = None
    
    # URLs
    listing_url: str
    image_urls: List[str] = Field(default_factory=list)
    
    # Seller info
    seller_info: Optional[str] = None
    
    # Items in listing
    guns: Optional[List[Gun]] = Field(default_factory=list)
    magazines: Optional[List[Magazine]] = Field(default_factory=list)
    ammunition: Optional[List[Ammunition]] = Field(default_factory=list)
    other_items: Optional[List[OtherItem]] = Field(default_factory=list) 