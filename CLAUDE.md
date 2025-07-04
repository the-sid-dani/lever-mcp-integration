# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server that integrates Lever ATS with Claude Desktop, enabling recruiters to manage their recruiting workflows through natural language commands.

## Development Setup

1. **Environment Setup**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configuration**:
   - Copy `.env.example` to `.env`
   - Add your Lever API key: `LEVER_API_KEY=your_api_key_here`

3. **Running the Server**:
   - The server runs through Claude Desktop configuration (see README.md)
   - For development/debugging: `python server.py`

## Architecture

### Core Components

1. **server.py**: Main MCP server implementation
   - Implements 16 recruiting tools as MCP endpoints
   - Handles rate limiting (8 req/sec, below Lever's 10 req/sec limit)
   - Manages tool routing and response formatting

2. **client.py** (244 lines): Async HTTP client for Lever API
   - Handles authentication and request construction
   - Implements retry logic and error handling
   - Supports pagination for list operations

### Key Implementation Patterns

- **Tool Organization**: Tools are grouped by domain (candidates, applications, interviews, etc.)
- **Error Handling**: Comprehensive error messages with actionable guidance
- **Rate Limiting**: Built-in rate limiter to respect API limits
- **Async Operations**: All API calls use aiohttp for concurrent operations
- **Response Formatting**: Consistent formatting for readability in Claude

### Important Constraints

1. **API Limits**: Lever API allows 10 requests/second; server limits to 8 for safety
2. **Pagination**: List operations return max 100 items per page
3. **Authentication**: Requires valid Lever API key with appropriate permissions
4. **No Testing Framework**: Manual testing through Claude Desktop integration
5. **No Text Search**: The Lever API `/opportunities` endpoint does NOT support a "query" parameter for text search. To search by name, we fetch all candidates and filter client-side. This is why searches may be slower than expected.
6. **No File Downloads**: Files cannot be downloaded directly through Claude Desktop due to authentication and file system limitations. Recruiters should access resumes and documents through the Lever web interface.

### Removed Tools
- lever_search_by_skills - Use advanced_search with skills parameter
- lever_search_by_location - Use advanced_search with locations parameter  
- lever_fuzzy_search - Use advanced_search with multiple criteria
- lever_download_file - Files must be accessed through Lever web interface
- lever_get_resume_url - Files must be accessed through Lever web interface
- lever_get_resume_content - Files must be accessed through Lever web interface
- lever_batch_company_stats - Had pagination errors, use find_by_company instead
- lever_filter_by_companies_efficient - Too complex, use find_by_company or advanced_search
- lever_company_search_simple - Query parameter doesn't work well, use find_by_company
- lever_debug_search - Not needed for recruiters, was for development only
- lever_create_application - POST operations not allowed by Lever API, applications must be created through web interface

## Common Development Tasks

When modifying or extending the server:

1. **Adding New Tools**: Follow the existing pattern in server.py
   - Define tool in the appropriate section
   - Implement handler method with proper error handling
   - Update README.md with usage examples

2. **Debugging**: 
   - Check logs from server.py output
   - Verify API key permissions in Lever
   - Test individual API calls using client.py methods

3. **API Integration**:
   - Lever API v1 documentation: https://hire.lever.co/developer/documentation
   - All endpoints require authentication via API key
   - Response data should be formatted for readability

## File Modification Guidelines

- **server.py**: Main logic for all recruiting tools
- **client.py**: Only modify for new API endpoints or authentication changes
- **README.md**: Update when adding new tools or changing setup procedures
- **requirements.txt**: Keep minimal - only essential dependencies

## No Automated Testing

This project relies on manual testing through Claude Desktop. When making changes:
1. Test each modified tool through Claude Desktop
2. Verify error handling with invalid inputs
3. Check rate limiting behavior under load
4. Ensure response formatting remains readable

## Known Limitations and Workarounds

### Lever API Restrictions
1. **No Stage Modifications**: The Lever API does not allow POST operations for stage changes, even with full API access. This is a platform-level restriction. Stage changes must be done manually through the Lever web interface.

2. **No Application Creation**: The Lever API does not allow POST operations to create new applications. Cross-posting candidates to multiple roles must be done through the Lever web interface.

3. **No Text Search**: The `/opportunities` endpoint doesn't support query parameters for text search. Name searches require fetching candidates and filtering locally.

### Large Result Sets
When dealing with 2000+ candidates:
- Use `lever_quick_find_candidate` for name searches (auto-limits to 100)
- Apply filters (stage, posting, tags) to reduce results
- Avoid fetching all pages to prevent context window issues