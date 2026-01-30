import os
import json
import re
from typing import Dict, Any, List, Literal
from pydantic import BaseModel, Field
from firecrawl import Firecrawl
from langchain_google_genai import ChatGoogleGenerativeAI
from state import MarketeerState


class CompanyAnalysis(BaseModel):
    """Structured output for company analysis."""
    company_name: str = Field(description="The company name extracted from the website")
    is_irish_sme: bool = Field(description="True if company is an Irish SME (based in Ireland, <200 employees)")
    tech_stack: List[str] = Field(description="List of all technologies mentioned (Angular, React, Vue, Node.js, etc.)")
    has_angular_debt: bool = Field(description="True if there are signs of Angular technical debt")
    grant_eligible: bool = Field(description="True if company is in Manufacturing or Internationally Traded Services")
    decision: Literal["PROCEED", "IGNORE"] = Field(description="PROCEED only if all conditions are met")


def scout_node(state: MarketeerState) -> Dict[str, Any]:
    """Scout Node: Scrapes the URL using Firecrawl and extracts clean markdown."""
    url = state["url"]
    
    try:
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if not api_key:
            raise ValueError("FIRECRAWL_API_KEY not found in environment variables")

        # Firecrawl v2 Python SDK (latest): https://docs.firecrawl.dev/sdks/python
        firecrawl = Firecrawl(api_key=api_key)
        result = firecrawl.scrape(url, formats=["markdown"])
        
        # Firecrawl returns markdown by default, check both possible response formats
        if isinstance(result, dict):
            raw_markdown = result.get("markdown") or result.get("content") or ""
        else:
            raw_markdown = str(result) if result else ""
        
        if not raw_markdown:
            raise ValueError(f"No markdown content extracted from {url}")
        
        return {
            "raw_markdown": raw_markdown
        }
    
    except Exception as e:
        # Basic error handling for scraping failures
        error_message = f"Scraping failed for {url}: {str(e)}"
        print(f"ERROR: {error_message}")
        return {
            "raw_markdown": None,
            "decision": "IGNORE"  # Fail gracefully by setting decision to IGNORE
        }


def analyst_node(state: MarketeerState) -> Dict[str, Any]:
    """Analyst Node: Uses Gemini 3 Flash to analyze the markdown and determine eligibility."""
    raw_markdown = state.get("raw_markdown")
    
    if not raw_markdown:
        return {
            "decision": "IGNORE",
            "company_name": None,
            "is_irish_sme": False,
            "tech_stack": [],
            "has_angular_debt": False,
            "grant_eligible": False
        }
    
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",  # Stable model per LangChain docs
            google_api_key=api_key,
            temperature=0
        )
        
        # Use structured output for reliable parsing
        structured_llm = llm.with_structured_output(CompanyAnalysis, method="json_schema")
        
        analysis_prompt = f"""Analyze the following company website content and extract key information.

Website Content:
{raw_markdown[:10000]}

CRITICAL INSTRUCTIONS FOR is_irish_sme:
Return TRUE if you see ANY of these indicators:
1. URL patterns: /en-ie/, /ie/, .ie domain, or links to Irish-specific pages
2. Text mentions: "Ireland", "Irish", "based in Ireland", "Irish company", "Irish SME"
3. Irish cities: Dublin, Cork, Galway, Limerick, Waterford, Kilkenny, etc.
4. Irish phone numbers: +353, or phone numbers starting with 353
5. Irish addresses or locations mentioned
6. Messages like "Hello, we notice you are visiting from Ireland" or "Go to IE site"
7. Company has separate Irish site/page (en-ie, /ie/, etc.) - this is a STRONG indicator
8. If company appears Irish-based and employee count is <200, return TRUE
9. If company appears Irish-based but no employee count mentioned, assume SME (most Irish companies are SMEs)

IMPORTANT: If the website has an Irish-specific version (like /en-ie/ or mentions "Ireland" in visitor detection), 
this is a STRONG indicator the company is Irish-based. Return TRUE for is_irish_sme in this case.

For tech_stack: 
- Look carefully through ALL content for technology mentions
- Include: Angular, AngularJS, React, Vue, Node.js, TypeScript, JavaScript, Python, Java, .NET, PHP, etc.
- Check job postings, blog posts, case studies, "About" sections, "Technology" pages
- If it's a software company, they likely use web technologies - look for clues

For has_angular_debt:
- Return TRUE if you see: AngularJS, Angular 1.x, "legacy Angular", "Angular migration", 
  "migrating from AngularJS", "Angular upgrade", "technical debt", job postings for Angular migration work

For grant_eligible:
- Return TRUE if company is in: Software development, SaaS, IT services, consulting, 
  Manufacturing, or any Internationally Traded Services sector
- Software companies typically qualify as Internationally Traded Services

For decision:
- PROCEED only if ALL are true: is_irish_sme AND "Angular" in tech_stack AND has_angular_debt AND grant_eligible
- Otherwise return IGNORE"""
        
        analysis = structured_llm.invoke(analysis_prompt)
        
        # Debug output to help diagnose issues
        print(f"DEBUG: Analysis result - is_irish_sme: {analysis.is_irish_sme}, "
              f"tech_stack: {analysis.tech_stack}, "
              f"has_angular_debt: {analysis.has_angular_debt}, "
              f"grant_eligible: {analysis.grant_eligible}")
        
        return {
            "company_name": analysis.company_name,
            "is_irish_sme": analysis.is_irish_sme,
            "tech_stack": analysis.tech_stack,
            "has_angular_debt": analysis.has_angular_debt,
            "grant_eligible": analysis.grant_eligible,
            "decision": analysis.decision
        }
    
    except Exception as e:
        error_message = f"Analysis failed: {str(e)}"
        print(f"ERROR: {error_message}")
        return {
            "decision": "IGNORE",
            "company_name": None,
            "is_irish_sme": False,
            "tech_stack": [],
            "has_angular_debt": False,
            "grant_eligible": False
        }


def outreach_node(state: MarketeerState) -> Dict[str, Any]:
    """Outreach Node: Drafts a personalized email to CTO if decision is PROCEED."""
    decision = state.get("decision")
    company_name = state.get("company_name", "there")
    tech_stack = state.get("tech_stack", [])
    has_angular_debt = state.get("has_angular_debt", False)
    
    if decision != "PROCEED":
        return {
            "outreach_draft": None
        }
    
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.7  # Slightly higher for more natural email tone
        )
        
        # Build context about the company
        tech_context = ", ".join(tech_stack[:5]) if tech_stack else "your technology stack"
        angular_context = "significant Angular technical debt" if has_angular_debt else "Angular in your stack"
        
        email_prompt = f"""Write a professional, concise 3-sentence email to the CTO of {company_name}.

Context:
- Company: {company_name}
- Technologies: {tech_context}
- Issue: {angular_context}
- They qualify for Enterprise Ireland Digital Discovery Grant (80% coverage)

Requirements:
- Subject line: "80% Grant Coverage for Angular Technical Debt Sprint"
- Opening: Address the CTO by company name
- Body: Mention the 80% grant coverage, Angular technical debt, and sprint contract offer
- Closing: Invite to a quick call
- Tone: Professional, no-nonsense, value-focused
- Length: Exactly 3 sentences (not counting greeting/closing)

Format:
Subject: [subject line]

Hi [company name] CTO,

[3-sentence email body]

[closing question]"""
        
        response = llm.invoke(email_prompt)
        outreach_draft = response.content.strip()
        
        return {
            "outreach_draft": outreach_draft
        }
    
    except Exception as e:
        # Fallback to simple template if LLM fails
        error_message = f"Email generation failed: {str(e)}"
        print(f"WARNING: {error_message}, using fallback template")
        
        outreach_draft = f"""Subject: 80% Grant Coverage for Angular Technical Debt Sprint

Hi {company_name} CTO,

We noticed your Angular technical debt and can help clear your backlog with a sprint contract covered 80% by the Enterprise Ireland Digital Discovery Grant.

This grant applies to Manufacturing and Internationally Traded Services companies, and we specialize in rapid Angular modernization sprints.

Interested in a quick call to discuss how we can leverage this grant to accelerate your technical roadmap?"""
        
        return {
            "outreach_draft": outreach_draft
        }
