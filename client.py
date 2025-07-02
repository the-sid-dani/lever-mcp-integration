"""
Async Lever API client with rate limiting and pagination support.
"""
import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
import json
from datetime import datetime


class AsyncLeverClient:
    """Async client for Lever API with rate limiting."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.lever.co/v1"
        self.rate_limiter = asyncio.Semaphore(8)  # 8 requests per second (safe under 10 limit)
        self.session = None
    
    async def __aenter__(self):
        """Create aiohttp session with timeout."""
        timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make rate-limited API request."""
        async with self.rate_limiter:
            url = f"{self.base_url}{endpoint}"
            
            try:
                async with self.session.request(
                    method, 
                    url, 
                    params=params, 
                    json=json_data
                ) as response:
                    # Check content type before parsing
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        text = await response.text()
                        raise Exception(f"Unexpected response type: {content_type}. Response: {text[:200]}")
                    
                    if response.status >= 400:
                        if isinstance(data, dict):
                            error_msg = data.get('message', f'API error: {response.status}')
                        else:
                            error_msg = f'API error: {response.status} - {str(data)}'
                        raise Exception(f"Lever API error: {error_msg}")
                    
                    return data
                    
            except aiohttp.ClientError as e:
                raise Exception(f"Network error: {str(e)}")
            except json.JSONDecodeError:
                raise Exception("Invalid JSON response from Lever API")
    
    async def get_opportunities(
        self, 
        query: Optional[str] = None,  # Note: API doesn't support query param, kept for backwards compatibility
        stage_id: Optional[str] = None,
        posting_id: Optional[str] = None,
        email: Optional[str] = None,
        tag: Optional[str] = None,
        origin: Optional[str] = None,
        limit: int = 25,
        offset: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get opportunities (candidates). 
        
        Note: The Lever API doesn't support text search via query parameter.
        To search by name, fetch all candidates and filter client-side.
        """
        params = {}
        # Query parameter not supported by API - will be ignored
        # Kept for backwards compatibility but should not be used
        if stage_id:
            params['stage_id'] = stage_id
        if posting_id:
            params['posting_id'] = posting_id
        if email:
            params['email'] = email
        if tag:
            params['tag'] = tag
        if origin:
            params['origin'] = origin
        if limit:
            params['limit'] = min(limit, 100)  # Max 100 per request
        if offset:
            params['offset'] = offset
            
        return await self._make_request('GET', '/opportunities', params=params)
    
    async def get_opportunity(self, opportunity_id: str) -> Dict[str, Any]:
        """Get a specific opportunity by ID."""
        return await self._make_request('GET', f'/opportunities/{opportunity_id}')
    
    async def update_opportunity_stage(
        self, 
        opportunity_id: str, 
        stage_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Move opportunity to a new stage."""
        data = {"stage": stage_id}
        if reason:
            data["reason"] = reason
            
        return await self._make_request(
            'POST', 
            f'/opportunities/{opportunity_id}/stage', 
            json_data=data
        )
    
    async def add_note(
        self, 
        opportunity_id: str, 
        note_text: str,
        author_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a note to an opportunity."""
        data = {"value": note_text}
        if author_email:
            data["author"] = author_email
            
        return await self._make_request(
            'POST', 
            f'/opportunities/{opportunity_id}/notes', 
            json_data=data
        )
    
    async def archive_opportunity(
        self, 
        opportunity_id: str, 
        reason_id: str
    ) -> Dict[str, Any]:
        """Archive an opportunity with a reason."""
        data = {"reason": reason_id}
        
        return await self._make_request(
            'POST', 
            f'/opportunities/{opportunity_id}/archived', 
            json_data=data
        )
    
    async def get_postings(
        self, 
        state: str = "published",
        limit: int = 25,
        offset: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get job postings."""
        params = {
            "state": state,
            "limit": min(limit, 100)
        }
        if offset:
            params["offset"] = offset
            
        return await self._make_request('GET', '/postings', params=params)
    
    async def get_stages(self) -> Dict[str, Any]:
        """Get all available stages."""
        return await self._make_request('GET', '/stages')
    
    async def get_archive_reasons(self) -> Dict[str, Any]:
        """Get all archive reasons."""
        return await self._make_request('GET', '/archive_reasons')
    
    async def get_opportunity_files(self, opportunity_id: str) -> Dict[str, Any]:
        """Get all files for an opportunity."""
        return await self._make_request('GET', f'/opportunities/{opportunity_id}/files')
    
    async def get_opportunity_resumes(self, opportunity_id: str) -> Dict[str, Any]:
        """Get all resumes for an opportunity."""
        return await self._make_request('GET', f'/opportunities/{opportunity_id}/resumes')
    
    async def download_file(self, download_url: str) -> bytes:
        """Download a file from Lever."""
        # Use existing session headers for authentication
        async with self.session.get(download_url) as response:
            if response.status >= 400:
                raise Exception(f"Failed to download file: {response.status}")
            return await response.read()
    
    async def get_opportunity_applications(self, opportunity_id: str) -> Dict[str, Any]:
        """Get all applications for an opportunity."""
        return await self._make_request('GET', f'/opportunities/{opportunity_id}/applications')
    
    async def get_application(self, opportunity_id: str, application_id: str) -> Dict[str, Any]:
        """Get specific application details."""
        return await self._make_request('GET', f'/opportunities/{opportunity_id}/applications/{application_id}')
    
    async def create_application(
        self, 
        opportunity_id: str,
        posting_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an application for a posting."""
        data = {"postingId": posting_id}
        if user_id:
            data["userId"] = user_id
        
        return await self._make_request(
            'POST',
            f'/opportunities/{opportunity_id}/applications',
            json_data=data
        )
    
    
    async def paginate_all(
        self, 
        fetch_func, 
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Helper to get all results across multiple pages."""
        all_results = []
        offset = None
        
        while True:
            if offset:
                kwargs['offset'] = offset
                
            response = await fetch_func(**kwargs)
            data = response.get('data', [])
            all_results.extend(data)
            
            if not response.get('hasNext', False):
                break
                
            # Get the next offset from the last item
            if data:
                offset = data[-1].get('id')
            else:
                break
                
        return all_results