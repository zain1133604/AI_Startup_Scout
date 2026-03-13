from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from typing import List, Optional, Dict, Union
import re
from typing import Dict, List

def parse_financial_string(val: Union[str, float, int]) -> float:
    """Converts strings like '46.1M' or '2B' into actual floats."""
    if val is None: return 0.0
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
    industry: str = "Unknown"
    website: Optional[Union[HttpUrl, str]] = None 
    summary: str = ""
    is_public: bool = Field(default=False)
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

    sources: Dict[str, str] = {}
    industry: Optional[str] = "Unknown"

    community_sentiment: str = "Mixed"
    vibe_score: float = 5.0
    top_complaint: str = "None"
    reddit_signal: str = "No data"
    investment_score: float = 0.0

    @model_validator(mode='after')
    def extract_from_notes(self) -> 'StartupState':
        text = self.manager_notes
        
        # Regex to capture numbers/suffixes
        def get_val(key):
            match = re.search(f"{key}:\\s*([\\$0-9\\.KMB]+)", text, re.I)
            return match.group(1) if match else None

        # NEW: Helper to capture text status (like Aggressive/Freeze)
        def get_text_val(key):
            match = re.search(f"{key}:\\s*([a-zA-Z]+)", text, re.I)
            return match.group(1).strip() if match else None

        # --- EXISTING FINANCIAL FIXES ---
        raw_fund = get_val("total_funding")
        if raw_fund: self.total_funding = parse_financial_string(raw_fund)

        raw_val = get_val("latest_valuation")
        if raw_val: self.latest_valuation = parse_financial_string(raw_val)

        raw_rev = get_val("annual_revenue")
        if raw_rev: self.annual_revenue = parse_financial_string(raw_rev)
        
        # --- NEW: HIRING PULSE FIXES ---
        self.hiring_status = get_text_val("hiring_status") or "Unknown"

        raw_roles = get_val("open_roles")
        if raw_roles:
            try:
                # We convert to float first in case the LLM returns "24.0"
                self.open_roles = int(float(raw_roles))
            except:
                self.open_roles = 0

        # --- EXISTING HEADCOUNT FIX ---
        if self.headcount == 0:
            hc_match = re.search(r"(?:headcount|employees|people):\s*(\d+)", text, re.I)
            if hc_match: 
                self.headcount = int(hc_match.group(1))

        return self
    # --- 🛡️ EXISTING VALIDATORS ---
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
  