# Web Search MCP Server (Tavily)

A production-ready Model Context Protocol (MCP) server providing internet search, web page content extraction, and English vocabulary discovery powered by the official Tavily Search API.

---

## 1. Purpose & Architecture

```text
mcpservers/web_search/
├── pyproject.toml                         # Package configuration & dependencies
├── README.md                              # Operational & integration guide
├── .gitignore                             # Git exclusion rules
├── src/
│   └── web_search_server/
│       ├── __init__.py                    # Package exports
│       ├── server.py                      # MCP server entry point & stdio transport
│       ├── config.py                      # Root .env discovery, credential masking & settings
│       ├── schemas.py                     # Pydantic models & SSRF-safe URL validation
│       ├── exceptions.py                  # Custom error hierarchy
│       ├── providers/
│       │   ├── __init__.py
│       │   └── tavily_provider.py         # Async Tavily client integration & error mapping
│       └── tools/
│           ├── __init__.py                # Tool registration with FastMCP / MCPServer
│           ├── search_web.py              # Tool 1: search_web
│           ├── get_page_content.py        # Tool 2: get_page_content
│           └── find_vocabulary.py         # Tool 3: find_vocabulary
└── tests/
    ├── conftest.py                        # Mock fixtures & Windows selector loop
    ├── test_search_web.py                 # Search argument validation & response tests
    ├── test_page_content.py               # Page content extraction & SSRF security tests
    ├── test_vocabulary.py                 # Vocabulary discovery & snippet parsing tests
    └── test_mcp_tools.py                  # Tool registration, error handling & integration tests
```

### Architectural Principles:
- **Clean Transport Separation**: Operates over `stdio`. All diagnostics and errors are strictly routed to `sys.stderr` to keep `sys.stdout` clean for JSON-RPC protocol frames.
- **Provider Encapsulation**: All Tavily SDK interactions and error transformations are encapsulated inside `providers/tavily_provider.py`.
- **Untrusted Input Protection**: Search results and web pages are treated as untrusted data. SSRF protection blocks requests to internal subnets, localhost, and cloud metadata endpoints.
- **Lazy Initialization**: Network calls and client initializations never execute during module import time.
- **Separation of Concerns**: This server only retrieves and discovers information. It does not store items to PostgreSQL or execute agent decision loops.

---

## 2. Prerequisites & Environment Configuration

### Prerequisites
- Python 3.11+
- Tavily API Key

### Root `.env` Discovery
The server automatically locates and loads the existing Tavily API key from the project root `.env` file or from the process environment:

```env
TAVILY_API_KEY=tvly-your-api-key-here
```
*(Case-insensitive: accepts both `TAVILY_API_KEY` and `tavily_api_key`).*

- **Path Resolution**: The server resolves the root directory by traversing upwards from the package module directory.
- **Secret Redaction**: The key is never logged, exposed in error messages, or transmitted in tool responses.
- **Optional Settings**:
  - `WEB_SEARCH_TIMEOUT_SECONDS`: Request timeout in seconds (Default: `30.0`).
  - `WEB_SEARCH_MAX_RESULTS_LIMIT`: Maximum allowed search results (Default: `10`).
  - `WEB_SEARCH_LOG_LEVEL`: Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`; Default: `INFO`).

---

## 3. Installation

From the project root:

```powershell
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -e mcpservers/web_search
```

Or install the required dependencies directly:
```powershell
pip install "mcp>=1.0.0" "tavily-python>=0.5.0" "pydantic>=2.0.0" "python-dotenv>=1.0.0" "httpx>=0.25.0"
```

---

## 4. Starting the Server

### Standalone stdio Execution
```powershell
python -m web_search_server.server
```

Or if installed via `pip install -e`:
```powershell
web-search-mcp-server
```

---

## 5. MCP Client Configuration

Add the server to your MCP client configuration (e.g., Claude Desktop, Cline, Antigravity):

```json
{
  "mcpServers": {
    "web_search": {
      "command": "python",
      "args": [
        "-m",
        "web_search_server.server"
      ],
      "cwd": "d:\\Voice Agent",
      "env": {
        "PYTHONPATH": "d:\\Voice Agent\\mcpservers\\web_search\\src"
      }
    }
  }
}
```

---

## 6. MCP Tools Reference

### Tool 1: `search_web`
Search the internet using Tavily and return relevant structured results.

| Argument | Type | Default | Description |
|---|---|---|---|
| `query` | string | *required* | The search query (1-500 characters). |
| `search_depth` | string | `"basic"` | `"basic"` (fast) or `"advanced"` (thorough). |
| `topic` | string | `"general"` | `"general"` or `"news"`. |
| `max_results` | integer | `5` | Maximum results to return (1-10). |
| `time_range` | string | `null` | `"day"`, `"week"`, `"month"`, or `"year"`. |
| `include_domains` | list[string] | `null` | Domains to prioritize or restrict to. |
| `exclude_domains` | list[string] | `null` | Domains to exclude from results. |
| `include_raw_content` | boolean | `false` | Whether to include full extracted content. |

**Output Structure:**
```json
{
  "success": true,
  "query": "effective communication in teams",
  "total_results": 3,
  "results": [
    {
      "title": "Effective Communication in the Workplace",
      "url": "https://example.com/effective-communication",
      "content": "Active listening and clarity are fundamental to team alignment...",
      "published_date": "2026-01-20",
      "score": 0.94,
      "raw_content": null
    }
  ],
  "message": null
}
```

---

### Tool 2: `get_page_content`
Retrieve and extract clean markdown text from a specific web page.

| Argument | Type | Default | Description |
|---|---|---|---|
| `url` | string | *required* | Absolute HTTP or HTTPS URL to extract. |
| `max_characters` | integer | `12000` | Character limit for extracted text (100-20000). |

**Security Controls:**
- Rejects unsupported schemes (`file:`, `javascript:`, `ftp:`, `data:`).
- Rejects SSRF targets: localhost, loopbacks (`127.0.0.1`, `::1`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and cloud metadata (`169.254.169.254`).

**Output Structure:**
```json
{
  "success": true,
  "url": "https://en.wikipedia.org/wiki/Spaced_repetition",
  "canonical_url": "https://en.wikipedia.org/wiki/Spaced_repetition",
  "title": "Spaced repetition - Wikipedia",
  "content": "# Spaced repetition\n\nSpaced repetition is an evidence-based learning technique...",
  "character_count": 5420,
  "truncated": false,
  "retrieval_metadata": {
    "source": "tavily_extract",
    "format": "markdown",
    "raw_length": 5420,
    "is_truncated": false
  }
}
```

---

### Tool 3: `find_vocabulary`
Discover English vocabulary words, idioms, definitions, and natural example sentences grounded in web sources.

| Argument | Type | Default | Description |
|---|---|---|---|
| `topic` | string | *required* | Subject or conversational theme (e.g. "job interview", "public speaking"). |
| `level` | string | `"intermediate"` | `"beginner"`, `"intermediate"`, or `"advanced"`. |
| `count` | integer | `5` | Number of items to retrieve (1-10). |
| `include_idioms` | boolean | `true` | Include idiomatic expressions. |
| `include_phrasal_verbs` | boolean | `true` | Include phrasal verbs. |
| `context` | string | `null` | Specific conversational scenario (e.g. "executive presentation"). |

**Output Structure:**
```json
{
  "success": true,
  "topic": "business negotiations",
  "level": "intermediate",
  "count": 2,
  "items": [
    {
      "word": "Compromise",
      "word_type": "noun",
      "meaning": "An agreement reached by each side making concessions.",
      "example_sentence": "Both parties reached a compromise during the contract dispute.",
      "synonyms": ["settlement", "middle ground"],
      "source_url": "https://dictionary.cambridge.org/dictionary/english/compromise",
      "difficulty": "intermediate",
      "difficulty_note": "Estimated intermediate level based on search context",
      "example_source_type": "source_grounded"
    }
  ],
  "instructions": "Vocabulary discovered from web resources. Save to Notes MCP server if revision tracking is desired."
}
```

---

## 7. Example Invocations

### 1. English Vocabulary & Idioms Search
```json
{
  "tool": "find_vocabulary",
  "arguments": {
    "topic": "storytelling and narratives",
    "level": "advanced",
    "count": 3,
    "context": "creative writing"
  }
}
```

### 2. Communication Tips Search
```json
{
  "tool": "search_web",
  "arguments": {
    "query": "best practices for concise communication in technical leadership",
    "search_depth": "advanced",
    "max_results": 4
  }
}
```

### 3. Reading Specific Web Page Content
```json
{
  "tool": "get_page_content",
  "arguments": {
    "url": "https://www.bbc.co.uk/learningenglish/features/the_english_we_speak",
    "max_characters": 8000
  }
}
```

---

## 8. Running Automated Tests

Run the unit test suite (runs 100% with mocks, consuming 0 Tavily credits):
```powershell
python -m pytest mcpservers/web_search/tests -v
```

All 19 tests verify:
- Search argument validation and bounded results.
- Empty search result handling.
- URL safety checks (rejection of non-HTTP schemes and private network SSRF targets).
- Page content character truncation and metadata.
- Vocabulary formatting and source URL preservation.
- Error handling for missing credentials, invalid API keys, rate limits, and timeouts.
- Redaction of credentials from all logs and errors.

To run the optional live integration test with your real API key:
```powershell
$env:RUN_TAVILY_INTEGRATION_TESTS="1"; python -m pytest mcpservers/web_search/tests/test_mcp_tools.py -k "test_live_tavily_integration" -v; Remove-Item Env:\RUN_TAVILY_INTEGRATION_TESTS
```

---

## 9. Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| `ConfigurationError: Missing required Tavily API key` | `TAVILY_API_KEY` is not present in the root `.env` or environment | Add `TAVILY_API_KEY=tvly-...` to your `.env` file in the project root. |
| `TavilyAuthError: Tavily authentication failed` | The configured API key is invalid or expired | Verify your API key on the [Tavily Dashboard](https://app.tavily.com). |
| `TavilyRateLimitError: credit quota exceeded` | Monthly request limit exceeded | Upgrade plan or wait for billing cycle reset on Tavily. |
| `ValidationError: Access to local loopback address is forbidden` | Target URL resolved to a private or internal IP address | Use a public HTTP or HTTPS web URL. |

