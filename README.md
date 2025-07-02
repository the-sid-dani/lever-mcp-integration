# Lever ATS MCP Server

An MCP (Model Context Protocol) server that integrates Lever ATS with Claude Desktop, enabling recruiters to manage their hiring pipeline through natural language conversations.

## Features

This MCP server provides the following tools for Claude Desktop:

### Core Tools
- **lever_search_candidates** - Search for candidates by query, stage, etc.
- **lever_get_candidate** - Get detailed information about a specific candidate
- **lever_add_note** - Add notes to candidate profiles
- **lever_list_open_roles** - List all published job postings
- **lever_find_candidates_for_role** - Find candidates for a specific role
- **lever_archive_candidate** - Archive candidates with reasons
- **lever_get_stages** - Get all available pipeline stages
- **lever_get_archive_reasons** - Get all archive reasons

### Advanced Search & Sourcing Tools 🔍
- **lever_advanced_search** - Multi-criteria search (companies, skills, locations, tags)
- **lever_find_by_company** - Source candidates from specific companies
- **lever_find_internal_referrals_for_role** - Find employees who can refer for a role

### File Management Tools 📄
- **lever_list_files** - List all files attached to a candidate (shows filename, type, size)

### Application Management Tools 📋
- **lever_list_applications** - List all applications for a candidate
- **lever_get_application** - Get specific application details
- **lever_create_application** - Apply candidate to a job posting


## Prerequisites

- Python 3.8+
- Lever API key (get from Lever Settings > Integrations > API)
- Claude Desktop installed

## Installation

1. Clone or download this repository:
```bash
cd "/Users/sid.dani/Desktop/4. Coding Projects/lever mcp - claude code"
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file from the example:
```bash
cp .env.example .env
```

5. Add your Lever API key to `.env`:
```
LEVER_API_KEY=your_actual_api_key_here
```

## Claude Desktop Configuration

1. Open Claude Desktop configuration file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the Lever MCP server configuration:

```json
{
  "mcpServers": {
    "lever-ats": {
      "command": "/path/to/your/venv/bin/python",
      "args": ["/Users/sid.dani/Desktop/4. Coding Projects/lever mcp - claude code/server.py"],
      "env": {
        "LEVER_API_KEY": "your_lever_api_key_here"
      }
    }
  }
}
```

**Important**: Update the paths:
- Replace `/path/to/your/venv/bin/python` with the actual path to your Python executable
- If using system Python, you can use `python3` or the full path

3. Restart Claude Desktop

## Usage Examples

Once configured, you can use natural language in Claude Desktop:

### Basic Searching
- "Search for senior engineers"
- "Find candidates from Google or Meta"
- "Show me candidates in the phone screen stage"
- "Quick find John Smith" (fast search for specific person)
- "Quick find jane@example.com" (email-based quick search)

### Advanced Search & Sourcing
- "Use advanced search to find Python developers from Google or Meta in San Francisco"
- "Search for candidates with skills: React, TypeScript, Node.js"
- "Find senior level candidates with AWS and Python experience"
- "Search candidates in London with remote work option"
- "Find candidates from companies: Google, Meta, Apple"
- "Find similar candidates to opportunity ID abc123"
- "Who can refer candidates for the Workplace Experience Manager role?"

### Managing Pipeline
- "Get details for candidate [opportunity_id]"
- "Add a note to candidate [opportunity_id]: Great technical skills"

### Viewing Roles and Pipeline
- "List all open roles"
- "Show candidates for posting [posting_id]"
- "What stages are available?"

### Archiving
- "Get archive reasons"
- "Archive candidate [opportunity_id] with reason [reason_id]"

### File Management
- "List all files for candidate [opportunity_id]"

### Application Management
- "List all applications for candidate [opportunity_id]"
- "Get application details [application_id] for candidate [opportunity_id]"
- "Apply candidate [opportunity_id] to posting [posting_id]"


## Important: Search Limitations

### Name Search Constraints
The Lever API does not support text search queries. When searching by name:
- The tool fetches candidates and filters locally
- Search is limited to first 500 candidates to prevent timeouts
- Results may be incomplete for common names

### Best Practices for Finding Candidates
1. **Use email search when possible** - Most reliable method
   - "Search for john.doe@example.com"
   - "Find candidate with email jane@company.com"

2. **Use the quick find tool for individual candidates**
   - "Quick find Svetlana Krockova"
   - "Quick find john@example.com"
   - Limited to first 300 candidates but faster

3. **Use tags and stages to narrow search**
   - "Find candidates tagged 'senior' in 'phone screen' stage"
   - "Search 'new applicant' stage for recent candidates"

4. **For company searches, use dedicated tools**
   - "Find candidates from Google"
   - "Filter by companies Microsoft, Apple"

## Troubleshooting

### MCP Server Not Showing in Claude
1. Check that the config file is valid JSON
2. Ensure all paths are absolute paths
3. Restart Claude Desktop completely

### API Errors
1. Verify your API key is correct
2. Check Lever API permissions
3. Ensure you're not hitting rate limits

### Search Not Finding Candidates
1. Try using email instead of name
2. Use lever_quick_find_candidate for faster results
3. Check if candidate might be archived
4. Ensure exact spelling of names

### Finding IDs
- Opportunity IDs are shown in search results
- Stage IDs can be found using `lever_get_stages`
- Posting IDs are shown in `lever_list_open_roles`
- Archive reason IDs are shown in `lever_get_archive_reasons`

## Development

To modify or extend the server:

1. The main server logic is in `server.py`
2. API client with rate limiting is in `client.py`
3. Add new tools by creating new `@mcp.tool()` decorated functions
4. Follow the existing pattern for error handling and response formatting

## Rate Limiting

The server implements rate limiting at 8 requests/second (below Lever's 10 req/sec limit) to ensure reliable operation.

## Security

- Never commit your `.env` file
- Keep your API key secure
- The server only has access to what your Lever API key permits

## Support

For issues with:
- Lever API: Check [Lever API Documentation](https://hire.lever.co/developer/documentation)
- MCP Protocol: See [MCP Documentation](https://github.com/modelcontextprotocol/servers)
- This server: Check the error messages in Claude Desktop