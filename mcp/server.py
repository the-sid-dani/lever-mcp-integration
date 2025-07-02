"""
Lever ATS MCP Server - Enables natural language recruiting workflows through Claude Desktop.
"""
import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from client import AsyncLeverClient

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp = FastMCP("Lever ATS")

# Get API key from environment
API_KEY = os.getenv("LEVER_API_KEY")
if not API_KEY:
    raise ValueError("LEVER_API_KEY environment variable is required")


def format_opportunity(opp: Dict[str, Any]) -> Dict[str, str]:
    """Format opportunity data for display."""
    # Ensure opp is a dictionary
    if not isinstance(opp, dict):
        return {
            "id": "",
            "name": "Error: Invalid data",
            "email": "N/A",
            "stage": "Unknown",
            "posting": "Unknown",
            "location": "Unknown",
            "organizations": "",
            "created": "Unknown"
        }
    
    # Get name directly from opportunity
    name = opp.get("name", "Unknown")
    
    # Get emails directly from opportunity
    emails = opp.get("emails", [])
    email = emails[0] if emails else "N/A"
    
    # Handle stage - it might be a string or a dict
    stage_info = opp.get("stage", "Unknown")
    if isinstance(stage_info, dict):
        stage_text = stage_info.get("text", "Unknown")
    else:
        stage_text = str(stage_info)
    
    # Handle posting - it might be missing or a dict
    posting_info = opp.get("posting")
    if isinstance(posting_info, dict):
        posting_text = posting_info.get("text", "Unknown")
    else:
        posting_text = "Unknown"
    
    # Get location directly from opportunity
    location = opp.get("location", "Unknown")
    
    return {
        "id": opp.get("id", ""),
        "name": name,
        "email": email,
        "stage": stage_text,
        "posting": posting_text,
        "location": location,
        "organizations": opp.get("headline", ""),  # This contains company history
        "created": datetime.fromtimestamp(opp.get("createdAt", 0) / 1000).strftime("%Y-%m-%d") if opp.get("createdAt") else "Unknown"
    }


def format_posting(posting: Dict[str, Any]) -> Dict[str, str]:
    """Format posting data for display."""
    return {
        "id": posting.get("id", ""),
        "title": posting.get("text", "Unknown"),
        "state": posting.get("state", "Unknown"),
        "location": posting.get("location", {}).get("name", "Unknown") if posting.get("location") else "Unknown",
        "team": posting.get("team", {}).get("text", "Unknown") if posting.get("team") else "Unknown",
        "url": posting.get("urls", {}).get("show", "") if posting.get("urls") else ""
    }


@mcp.tool()
async def lever_search_candidates(
    query: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Search for candidates in Lever ATS.
    
    Args:
        query: Search query (searches names, emails, tags, etc.)
        stage: Filter by stage name (e.g., "Phone Screen", "Onsite")
        limit: Maximum number of results to return (default 100)
    
    Returns:
        JSON formatted list of candidates with their details
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # If stage name provided, we might need to get stage ID
            stage_id = None
            if stage:
                # For now, pass stage as-is and let Lever handle it
                # In future, could map common stage names to IDs
                stage_id = stage
            
            # Check if query looks like an email
            email_filter = None
            if query and "@" in query:
                email_filter = query
            
            # Simple implementation - if we have an email, use it
            if email_filter:
                response = await client.get_opportunities(
                    email=email_filter,
                    stage_id=stage_id,
                    limit=limit
                )
                all_opportunities = response.get("data", [])
            elif query:
                # For name searches, we have to fetch and filter locally
                # This is a limitation of the Lever API
                all_opportunities = []
                offset = None
                pages_checked = 0
                max_pages = 2  # Only check first 200 candidates to prevent timeout
                
                query_lower = query.lower()
                
                while pages_checked < max_pages and len(all_opportunities) < limit:
                    response = await client.get_opportunities(
                        stage_id=stage_id,
                        limit=100,
                        offset=offset
                    )
                    
                    candidates = response.get("data", [])
                    if not candidates:
                        break
                    
                    # Filter candidates by name
                    for c in candidates:
                        if not isinstance(c, dict):
                            continue
                            
                        # Check name in opportunity
                        name = c.get("name", "").lower()
                        
                        if query_lower in name:
                            all_opportunities.append(c)
                            if len(all_opportunities) >= limit:
                                break
                    
                    pages_checked += 1
                    if not response.get("hasNext", False):
                        break
                    
                    offset = response.get("next")
                    if not offset:
                        break
                
                # Add warning if no results
                if not all_opportunities and pages_checked >= max_pages:
                    hit_limit = True
                else:
                    hit_limit = False
            else:
                # No search criteria, just get candidates
                response = await client.get_opportunities(
                    stage_id=stage_id,
                    limit=limit
                )
                all_opportunities = response.get("data", [])
                hit_limit = False
            
            # Limit final results to requested amount
            all_opportunities = all_opportunities[:limit]
            
            # Format results
            results = {
                "count": len(all_opportunities),
                "query": query,
                "candidates": [format_opportunity(opp) for opp in all_opportunities]
            }
            
            # Add warning if we hit the fetch limit
            if hit_limit:
                results["warning"] = (
                    "Search limited to first 200 candidates. "
                    "Results may be incomplete. Try using email search or tags for better results."
                )
                results["total_scanned"] = pages_checked * 100 if 'pages_checked' in locals() else 0
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_quick_find_candidate(
    name_or_email: str
) -> str:
    """
    Quick search for a specific candidate by name or email.
    This is optimized for finding individual candidates quickly.
    
    Args:
        name_or_email: Candidate's name or email address
    
    Returns:
        First few matching candidates (limited search scope)
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # If it looks like an email, use email search
            if "@" in name_or_email:
                response = await client.get_opportunities(
                    email=name_or_email,
                    limit=10
                )
                candidates = response.get("data", [])
                
                results = {
                    "count": len(candidates),
                    "search_type": "email",
                    "query": name_or_email,
                    "candidates": [format_opportunity(c) for c in candidates]
                }
                return json.dumps(results, indent=2)
            
            # Otherwise, do a limited name search
            query_lower = name_or_email.lower()
            matched = []
            offset = None
            pages_checked = 0
            max_pages = 3  # Only check first 300 candidates
            
            while pages_checked < max_pages:
                response = await client.get_opportunities(
                    limit=100,
                    offset=offset
                )
                
                candidates = response.get("data", [])
                if not candidates:
                    break
                
                # Quick scan for name matches
                for c in candidates:
                    if not isinstance(c, dict):
                        continue
                    
                    c_name = c.get("name", "").lower()
                    
                    if query_lower in c_name or c_name in query_lower:
                        matched.append(c)
                        if len(matched) >= 5:  # Return first 5 matches
                            break
                
                if len(matched) >= 5:
                    break
                
                pages_checked += 1
                if not response.get("hasNext", False):
                    break
                    
                offset = response.get("next")
                if not offset:
                    break
            
            results = {
                "count": len(matched),
                "search_type": "quick_name_search",
                "query": name_or_email,
                "candidates": [format_opportunity(c) for c in matched],
                "note": f"Quick search checked first {pages_checked * 100} candidates. For comprehensive search, use email if available."
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_find_candidate_in_posting(
    name: str,
    posting_id: str,
    stage: Optional[str] = None
) -> str:
    """
    Find a specific candidate within a job posting.
    More efficient than general search when you know the posting.
    
    Args:
        name: Candidate's name to search for
        posting_id: The specific job posting ID
        stage: Optional stage to narrow search (e.g., "new applicant")
    
    Returns:
        Matching candidates in the specified posting
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            name_lower = name.lower()
            matched = []
            offset = None
            total_checked = 0
            
            # Search with posting filter - much more targeted
            while total_checked < 1000:  # Can check more when filtered by posting
                response = await client.get_opportunities(
                    posting_id=posting_id,
                    stage_id=stage,
                    limit=100,
                    offset=offset
                )
                
                candidates = response.get("data", [])
                if not candidates:
                    break
                
                total_checked += len(candidates)
                
                # Check each candidate
                for c in candidates:
                    c_name = c.get("name", "").lower()
                    # More flexible matching
                    name_parts = name_lower.split()
                    if any(part in c_name for part in name_parts) or name_lower in c_name:
                        matched.append(c)
                
                if not response.get("hasNext", False):
                    break
                    
                offset = response.get("next")
                if not offset:
                    break
            
            results = {
                "count": len(matched),
                "posting_id": posting_id,
                "total_checked": total_checked,
                "query": name,
                "candidates": [format_opportunity(c) for c in matched]
            }
            
            if not matched and total_checked > 0:
                results["note"] = f"No matches found for '{name}' among {total_checked} candidates in this posting"
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_get_candidate(opportunity_id: str) -> str:
    """
    Get detailed information about a specific candidate.
    
    Args:
        opportunity_id: The Lever opportunity ID
    
    Returns:
        Detailed candidate information including stage, notes, and application details
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            response = await client.get_opportunity(opportunity_id)
            opportunity = response.get("data", {})
            
            # Get data directly from opportunity
            name = opportunity.get("name", "Unknown")
            emails = opportunity.get("emails", [])
            location = opportunity.get("location", "Unknown")
            
            # Format detailed view
            stage_info = opportunity.get("stage", {})
            if isinstance(stage_info, dict):
                stage_current = stage_info.get("text", "Unknown")
                stage_id = stage_info.get("id", "")
            else:
                stage_current = str(stage_info)
                stage_id = ""
            
            owner_info = opportunity.get("owner")
            if isinstance(owner_info, dict):
                owner_name = owner_info.get("name", "Unassigned")
            else:
                owner_name = "Unassigned"
            
            # Extract organizations/companies from headline
            headline = opportunity.get("headline", "")
            organizations = []
            if headline:
                # Split by comma and clean up
                orgs = [org.strip() for org in headline.split(",")]
                organizations = orgs
            
            # Get links (LinkedIn, etc.)
            links = opportunity.get("links", [])
            
            # Get phones
            phones = opportunity.get("phones", [])
            
            result = {
                "basic_info": format_opportunity(opportunity),
                "contact": {
                    "emails": emails,
                    "phones": phones,
                    "location": location
                },
                "stage": {
                    "current": stage_current,
                    "id": stage_id
                },
                "tags": opportunity.get("tags", []),
                "sources": opportunity.get("sources", []),
                "origin": opportunity.get("origin", "Unknown"),
                "owner": owner_name,
                "headline": headline,
                "organizations": organizations,
                "links": links,
                "applications": len(opportunity.get("applications", [])),
                "createdAt": datetime.fromtimestamp(opportunity.get("createdAt", 0) / 1000).strftime("%Y-%m-%d %H:%M") if opportunity.get("createdAt") else "Unknown",
                "archived": opportunity.get("archived", {}) if opportunity.get("archived") else None
            }
            
            return json.dumps(result, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})




@mcp.tool()
async def lever_add_note(
    opportunity_id: str,
    note: str,
    author_email: Optional[str] = None
) -> str:
    """
    Add a note to a candidate's profile.
    
    Args:
        opportunity_id: The Lever opportunity ID
        note: The note text to add
        author_email: Optional email of the note author
    
    Returns:
        Confirmation that the note was added
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Add the note
            await client.add_note(opportunity_id, note, author_email)
            
            # Get opportunity details for confirmation
            response = await client.get_opportunity(opportunity_id)
            opportunity = response.get("data", {})
            
            result = {
                "success": True,
                "candidate": opportunity.get("name", "Unknown"),
                "note_added": note,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return json.dumps(result, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_list_open_roles() -> str:
    """
    List all open job postings.
    
    Returns:
        List of published job postings with details
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            response = await client.get_postings(state="published", limit=50)
            
            postings = response.get("data", [])
            
            results = {
                "count": len(postings),
                "hasMore": response.get("hasNext", False),
                "roles": [format_posting(posting) for posting in postings]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_find_candidates_for_role(posting_id: str, limit: int = 100) -> str:
    """
    Find all candidates for a specific job posting.
    
    Args:
        posting_id: The Lever posting ID
        limit: Maximum number of results (default 100)
    
    Returns:
        List of candidates who have applied to this role
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            response = await client.get_opportunities(
                posting_id=posting_id,
                limit=limit
            )
            
            opportunities = response.get("data", [])
            
            # Group by stage for pipeline view
            stages = {}
            for opp in opportunities:
                stage_info = opp.get("stage", "Unknown")
                if isinstance(stage_info, dict):
                    stage_name = stage_info.get("text", "Unknown")
                else:
                    stage_name = str(stage_info)
                
                if stage_name not in stages:
                    stages[stage_name] = []
                stages[stage_name].append(format_opportunity(opp))
            
            results = {
                "total_candidates": len(opportunities),
                "hasMore": response.get("hasNext", False),
                "pipeline": stages,
                "all_candidates": [format_opportunity(opp) for opp in opportunities]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_archive_candidate(
    opportunity_id: str,
    reason_id: str
) -> str:
    """
    Archive a candidate with a specific reason.
    
    Args:
        opportunity_id: The Lever opportunity ID
        reason_id: The archive reason ID
    
    Returns:
        Confirmation of archival
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Get candidate info before archiving
            opp_response = await client.get_opportunity(opportunity_id)
            opportunity = opp_response.get("data", {})
            
            # Archive the candidate
            await client.archive_opportunity(opportunity_id, reason_id)
            
            result = {
                "success": True,
                "candidate": opportunity.get("name", "Unknown"),
                "archived": True,
                "reason_id": reason_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return json.dumps(result, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_get_stages() -> str:
    """
    Get all available pipeline stages.
    
    Returns:
        List of all stages with their IDs and names
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            response = await client.get_stages()
            
            stages = response.get("data", [])
            
            results = {
                "count": len(stages),
                "stages": [
                    {
                        "id": stage.get("id", ""),
                        "text": stage.get("text", ""),
                        "type": stage.get("type", "")
                    }
                    for stage in stages
                ]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_get_archive_reasons() -> str:
    """
    Get all available archive reasons.
    
    Returns:
        List of archive reasons with their IDs
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            response = await client.get_archive_reasons()
            
            reasons = response.get("data", [])
            
            results = {
                "count": len(reasons),
                "reasons": [
                    {
                        "id": reason.get("id", ""),
                        "text": reason.get("text", "")
                    }
                    for reason in reasons
                ]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_advanced_search(
    companies: Optional[str] = None,
    skills: Optional[str] = None,
    locations: Optional[str] = None,
    stage: Optional[str] = None,
    tags: Optional[str] = None,
    posting_id: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Advanced multi-criteria candidate search with flexible matching.
    
    Args:
        companies: Comma-separated list of company names (matches ANY)
        skills: Comma-separated list of skills (matches ANY)
        locations: Comma-separated list of locations (matches ANY)
        stage: Filter by specific stage
        tags: Comma-separated list of tags (matches ANY)
        posting_id: Filter by specific job posting
        limit: Maximum results (default 100)
    
    Returns:
        Candidates matching ALL specified criteria types (AND between types, OR within types)
        Example: (company1 OR company2) AND (skill1 OR skill2) AND (location1 OR location2)
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Parse search criteria
            company_list = [c.strip().lower() for c in companies.split(",")] if companies else []
            skill_list = [s.strip().lower() for s in skills.split(",")] if skills else []
            location_list = [l.strip().lower() for l in locations.split(",")] if locations else []
            tag_list = [t.strip().lower() for t in tags.split(",")] if tags else []
            
            # Get all candidates with pagination
            all_candidates = []
            offset = None
            max_fetch = limit * 10 if (companies or skills or locations) else limit
            
            while len(all_candidates) < max_fetch:
                response = await client.get_opportunities(
                    stage_id=stage,
                    posting_id=posting_id,
                    tag=tags.split(",")[0] if tags else None,  # API only supports single tag
                    limit=100,
                    offset=offset
                )
                
                candidates = response.get("data", [])
                
                # Client-side filtering for all criteria
                filtered_candidates = []
                for c in candidates:
                    if not isinstance(c, dict):
                        continue
                        
                    # Convert candidate data to lowercase for comparison
                    c_name = c.get("name", "").lower()
                    c_emails = c.get("emails", [])
                    if not isinstance(c_emails, list):
                        c_emails = []
                    c_emails = [e.lower() for e in c_emails if isinstance(e, str)]
                    
                    c_tags = c.get("tags", [])
                    if not isinstance(c_tags, list):
                        c_tags = []
                    c_tags = [t.lower() for t in c_tags if isinstance(t, str)]
                    
                    c_location = c.get("location", "")
                    if isinstance(c_location, dict):
                        c_location = c_location.get("name", "")
                    c_location = str(c_location).lower()
                    
                    # Get company info from headline field
                    c_headline = str(c.get("headline", "")).lower()
                    c_organizations = c.get("organizations", [])
                    if isinstance(c_organizations, str):
                        c_organizations = [c_organizations]
                    elif not isinstance(c_organizations, list):
                        c_organizations = []
                    c_organizations = [str(o).lower() for o in c_organizations]
                    
                    # Combine all text for skills search
                    c_all_text = f"{c_name} {' '.join(c_emails)} {' '.join(c_tags)} {c_headline} {' '.join(c_organizations)}".lower()
                    
                    # Check each criteria
                    # Company match: check in headline (primary) or organizations
                    company_match = not company_list or any(comp in c_headline for comp in company_list) or any(comp in org for comp in company_list for org in c_organizations)
                    
                    # Skills match: ANY skill match (OR logic)
                    skill_match = not skill_list or any(skill in c_all_text for skill in skill_list)
                    
                    # Location match: ANY location match
                    location_match = not location_list or any(loc in c_location for loc in location_list)
                    
                    # Tag match: ANY tag match
                    tag_match = not tag_list or any(tag in c_tags for tag in tag_list)
                    
                    if company_match and skill_match and location_match and tag_match:
                        filtered_candidates.append(c)
                
                all_candidates.extend(filtered_candidates)
                
                if not response.get("hasNext", False):
                    break
                    
                offset = response.get("next")
                if not offset:
                    break
            
            # Limit final results
            all_candidates = all_candidates[:limit]
            
            results = {
                "count": len(all_candidates),
                "search_criteria": {
                    "companies": companies,
                    "skills": skills,
                    "locations": locations,
                    "stage": stage,
                    "tags": tags,
                    "posting": posting_id
                },
                "candidates": [format_opportunity(opp) for opp in all_candidates]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_find_by_company(
    companies: str,
    current_only: bool = True,
    limit: int = 100
) -> str:
    """
    Find candidates from specific companies.
    
    Args:
        companies: Comma-separated list of company names (e.g., "Google, Meta, Apple")
        current_only: Only current employees (default True)
        limit: Maximum results (default 100)
    
    Returns:
        Candidates who work(ed) at specified companies
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Parse company list
            company_list = [c.strip() for c in companies.split(",")]
            
            # Search for each company
            all_candidates = []
            
            for company in company_list:
                query = f'"{company}"'  # Exact match
                if current_only:
                    query += " current"
                
                response = await client.get_opportunities(
                    query=query,
                    limit=limit
                )
                
                candidates = response.get("data", [])
                
                # Filter to ensure company match in headline or tags
                for candidate in candidates:
                    headline = candidate.get("headline", "").lower()
                    tags = [t.lower() for t in candidate.get("tags", [])]
                    
                    # Check for exact or partial company match
                    company_found = False
                    if headline:
                        # Split headline by comma to get individual companies
                        headline_companies = [c.strip().lower() for c in headline.split(",")]
                        for hc in headline_companies:
                            if company.lower() in hc or hc in company.lower():
                                company_found = True
                                break
                    
                    if company_found or any(company.lower() in tag for tag in tags):
                        candidate["matched_company"] = company
                        candidate["full_headline"] = candidate.get("headline", "")
                        all_candidates.append(candidate)
            
            # Remove duplicates
            seen_ids = set()
            unique_candidates = []
            for c in all_candidates:
                if c["id"] not in seen_ids:
                    seen_ids.add(c["id"])
                    unique_candidates.append(c)
            
            # Limit results
            unique_candidates = unique_candidates[:limit]
            
            results = {
                "count": len(unique_candidates),
                "searched_companies": company_list,
                "current_employees_only": current_only,
                "candidates": [
                    {
                        **format_opportunity(c),
                        "matched_company": c.get("matched_company", "Unknown"),
                        "all_organizations": c.get("full_headline", c.get("headline", ""))
                    }
                    for c in unique_candidates
                ]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_find_internal_referrals_for_role(
    posting_id: str,
    limit: int = 100
) -> str:
    """
    Find internal employees who could refer candidates for a specific role.
    
    Args:
        posting_id: The job posting ID to find referrals for
        limit: Maximum results (default 20)
    
    Returns:
        Internal candidates/employees who might know good referrals
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # First get the posting details
            postings_response = await client.get_postings(limit=100)
            postings = postings_response.get("data", [])
            
            target_posting = None
            for posting in postings:
                if posting.get("id") == posting_id:
                    target_posting = posting
                    break
            
            if not target_posting:
                return json.dumps({"error": f"Posting {posting_id} not found"})
            
            posting_title = target_posting.get("text", "")
            posting_team = target_posting.get("team", {}).get("text", "") if target_posting.get("team") else ""
            
            # Search for internal employees with related experience
            # Look for candidates with "employee" or "internal" tags
            internal_query = "employee OR internal OR referral"
            
            response = await client.get_opportunities(
                query=internal_query,
                limit=limit * 2
            )
            
            candidates = response.get("data", [])
            
            # Filter for likely employees who could refer
            potential_referrers = []
            
            for candidate in candidates:
                tags = [t.lower() for t in candidate.get("tags", [])]
                headline = candidate.get("headline", "").lower()
                
                # Check if they're marked as internal/employee
                is_internal = (
                    "employee" in tags or
                    "internal" in tags or
                    "referral" in " ".join(tags) or
                    "current" in headline
                )
                
                # Check if they're in a related team/role
                is_related = (
                    posting_team.lower() in headline or
                    posting_team.lower() in " ".join(tags) or
                    any(keyword in headline for keyword in posting_title.lower().split())
                )
                
                if is_internal or is_related:
                    candidate["referral_relevance"] = "internal" if is_internal else "related"
                    potential_referrers.append(candidate)
            
            # Limit results
            potential_referrers = potential_referrers[:limit]
            
            results = {
                "count": len(potential_referrers),
                "role": posting_title,
                "team": posting_team,
                "potential_referrers": [
                    {
                        **format_opportunity(c),
                        "relevance": c.get("referral_relevance", "unknown")
                    }
                    for c in potential_referrers
                ]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_list_files(opportunity_id: str) -> str:
    """
    List all files attached to a candidate.
    
    Args:
        opportunity_id: The Lever opportunity ID
    
    Returns:
        List of all files with metadata
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Try both endpoints - files and resumes
            all_files = []
            
            # Try files endpoint
            try:
                files_response = await client.get_opportunity_files(opportunity_id)
                files = files_response.get("data", [])
                for f in files:
                    f["source"] = "files"
                all_files.extend(files)
            except Exception as files_error:
                # Log but continue
                pass
            
            # Try resumes endpoint
            try:
                resumes_response = await client.get_opportunity_resumes(opportunity_id)
                resumes = resumes_response.get("data", [])
                for r in resumes:
                    r["source"] = "resumes"
                    # Add debug info to see full resume structure
                all_files.extend(resumes)
            except Exception as resumes_error:
                # Log but continue
                pass
            
            # Get candidate info for context
            opp_response = await client.get_opportunity(opportunity_id)
            opportunity = opp_response.get("data", {})
            
            results = {
                "candidate": opportunity.get("name", "Unknown"),
                "file_count": len(all_files),
                "files": [
                    {
                        "id": f.get("id", ""),
                        "filename": f.get("file", {}).get("name", "") if "file" in f else f.get("name", f.get("filename", "Unknown")),
                        "type": f.get("file", {}).get("ext", "") if "file" in f else f.get("type", f.get("mimetype", "Unknown")),
                        "size": f.get("file", {}).get("size", 0) if "file" in f else f.get("size", 0),
                        "uploaded_at": datetime.fromtimestamp(f.get("createdAt", 0) / 1000).strftime("%Y-%m-%d %H:%M") if f.get("createdAt") else "Unknown",
                        "download_url": f.get("file", {}).get("downloadUrl", "") if "file" in f else f.get("downloadUrl", f.get("url", "")),
                        "source": f.get("source", "unknown")
                    }
                    for f in all_files
                ]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})








@mcp.tool()
async def lever_list_applications(opportunity_id: str) -> str:
    """
    List all applications for a candidate.
    
    Args:
        opportunity_id: The Lever opportunity ID
    
    Returns:
        List of all applications with details
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Get candidate info
            opp_response = await client.get_opportunity(opportunity_id)
            opportunity = opp_response.get("data", {})
            
            # Get applications
            response = await client.get_opportunity_applications(opportunity_id)
            applications = response.get("data", [])
            
            results = {
                "candidate": opportunity.get("name", "Unknown"),
                "application_count": len(applications),
                "applications": [
                    {
                        "id": app.get("id", ""),
                        "posting": app.get("posting", {}).get("text", "Unknown") if app.get("posting") else "Unknown",
                        "posting_id": app.get("posting", {}).get("id", "") if app.get("posting") else "",
                        "status": app.get("status", "Unknown"),
                        "created_at": datetime.fromtimestamp(app.get("createdAt", 0) / 1000).strftime("%Y-%m-%d %H:%M") if app.get("createdAt") else "Unknown",
                        "user": app.get("user", {}).get("name", "Unknown") if app.get("user") else "System"
                    }
                    for app in applications
                ]
            }
            
            return json.dumps(results, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_get_application(
    opportunity_id: str,
    application_id: str
) -> str:
    """
    Get detailed information about a specific application.
    
    Args:
        opportunity_id: The Lever opportunity ID
        application_id: The specific application ID
    
    Returns:
        Detailed application information
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Get application details
            application = await client.get_application(opportunity_id, application_id)
            
            # Get candidate info for context
            opp_response = await client.get_opportunity(opportunity_id)
            opportunity = opp_response.get("data", {})
            
            result = {
                "candidate": opportunity.get("name", "Unknown"),
                "application": {
                    "id": application.get("id", ""),
                    "posting": {
                        "id": application.get("posting", {}).get("id", ""),
                        "title": application.get("posting", {}).get("text", "Unknown"),
                        "team": application.get("posting", {}).get("team", {}).get("text", "Unknown") if application.get("posting", {}).get("team") else "Unknown"
                    },
                    "status": application.get("status", "Unknown"),
                    "created_at": datetime.fromtimestamp(application.get("createdAt", 0) / 1000).strftime("%Y-%m-%d %H:%M") if application.get("createdAt") else "Unknown",
                    "created_by": application.get("user", {}).get("name", "Unknown") if application.get("user") else "System",
                    "type": application.get("type", "Unknown"),
                    "posting_owner": application.get("postingOwner", {}).get("name", "Unknown") if application.get("postingOwner") else "Unknown"
                }
            }
            
            return json.dumps(result, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def lever_create_application(
    opportunity_id: str,
    posting_id: str,
    user_id: Optional[str] = None
) -> str:
    """
    Apply a candidate to a job posting.
    
    Args:
        opportunity_id: The candidate's opportunity ID
        posting_id: The job posting ID to apply to
        user_id: Optional user ID who is creating the application
    
    Returns:
        Confirmation of application creation
    """
    try:
        async with AsyncLeverClient(API_KEY) as client:
            # Get candidate and posting info
            opp_response = await client.get_opportunity(opportunity_id)
            opportunity = opp_response.get("data", {})
            
            # Create the application
            result = await client.create_application(
                opportunity_id=opportunity_id,
                posting_id=posting_id,
                user_id=user_id
            )
            
            application = {
                "success": True,
                "candidate": opportunity.get("name", "Unknown"),
                "application_id": result.get("id", ""),
                "posting": result.get("posting", {}).get("text", "Unknown") if result.get("posting") else "Unknown",
                "status": result.get("status", "active"),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return json.dumps(application, indent=2)
            
    except Exception as e:
        return json.dumps({"error": str(e)})


# Run the server
if __name__ == "__main__":
    mcp.run()