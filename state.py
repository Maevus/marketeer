from typing import TypedDict, List, Literal, Optional


class MarketeerState(TypedDict):
    """State for the Marketeer graph workflow."""
    url: str
    raw_markdown: Optional[str]
    company_name: Optional[str]
    is_irish_sme: Optional[bool]
    tech_stack: List[str]
    has_angular_debt: Optional[bool]
    grant_eligible: Optional[bool]
    decision: Optional[Literal["PROCEED", "IGNORE"]]
    outreach_draft: Optional[str]
