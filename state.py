from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import List, Optional, Dict, Union, Annotated, Any
import re
import operator

def parse_financial_string(val: Union[str, float, int]) -> float:
    """Converts strings like '46.1M' or '2B' into actual floats."""
    if val is None or val == "": return 0.0
    if isinstance(val, (float, int)): return float(val)
    
    clean_val = str(val).replace('$', '').replace(',', '').strip().upper()
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000, 'T': 1_000_000_000_000}
    
    for suffix, mult in multipliers.items():
        if clean_val.endswith(suffix):
            try: return float(clean_val.replace(suffix, '')) * mult
            except: return 0.0
    try: return float(clean_val)
    except: return 0.0

class Founder(BaseModel):
    name: str
    role: Optional[str] = "Founder"  
    bio: Optional[str] = "Not provided"
    linkedin: Optional[str] = "Not provided"

class FundingRound(BaseModel):
    round_name: str = Field(default="Unknown Round")
    amount: float = Field(default=0.0)    
    date: str = Field(default="Date not found")
    investors: List[str] = []

class Competitor(BaseModel):
    name: str
    description: str = "No description" 
    threat_level: str = "Medium"        
    core_feature: Optional[str] = "N/A" 
    moat_vs_target: Optional[str] = "N/A" 

class Citation(BaseModel):
    source_url: str
    fact: str

class StartupState(BaseModel):
    """The Single Source of Truth for the entire Scout Squad."""
    
    company_name: str
    industry: Optional[str] = "Unknown"
    website: Optional[Union[HttpUrl, str]] = None 
    summary: str = ""
    is_public: bool = False
    ticker: Optional[str] = None
    
    founders: List[Founder] = []
    headcount: int = 0
    headcount_source: str = "Unknown"

    total_funding: float = 0.0
    latest_valuation: Optional[float] = 0.0
    annual_revenue: float = 0.0 
    estimated_monthly_burn: float = 0.0
    runway_months: float = 0.0
    arr_multiple: float = 0.0
    
    net_profit: float = 0.0 
    eps_basic: float = 0.0 
    eps_diluted: float = 0.0
    cash_on_hand: float = 0.0
    
    cac: float = 0.0
    payback_period: float = 0.0
    
    funding_history: List[FundingRound] = Field(default_factory=list)
    competitors: List[Competitor] = []
    moat_description: str = ""
    
    manager_notes: str = ""
    critic_verdict: str = ""
    citations: List[Citation] = []

    hiring_status: str = "Unknown"  
    open_roles: int = 0

    sources: Dict[str, Optional[str]] = Field(default_factory=lambda: {
            "total_funding": "Not Found",
            "latest_valuation": "Not Found",
            "annual_revenue": "Not Found",
            "headcount": "Not Found"
        })

    community_sentiment: str = "Mixed"
    vibe_score: float = 5.0
    top_complaint: str = "None"
    reddit_signal: str = "No data"
    investment_score: float = 0.0

    @field_validator('is_public', mode='before')
    @classmethod
    def force_bool(cls, v):
        if isinstance(v, str):
            return v.lower() in ("yes", "true", "t", "1")
        return bool(v)

    @field_validator('total_funding', 'latest_valuation', 'annual_revenue', mode='before')
    @classmethod
    def validate_financials(cls, v):
        return parse_financial_string(v)

    @field_validator('founders', mode='before')
    @classmethod
    def fix_founder_list(cls, v):
        if isinstance(v, list):
            return [{"name": item} if isinstance(item, str) else item for item in v]
        return v

    @field_validator('competitors', mode='before')
    @classmethod
    def fix_competitor_list(cls, v):
        if isinstance(v, list):
            return [{"name": item, "description": "N/A", "threat_level": "Med"} if isinstance(item, str) else item for item in v]
        return v

    class Config:
        arbitrary_types_allowed = True
        extra = "ignore"