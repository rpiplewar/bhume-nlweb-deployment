# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Commands

### Running the Application
```bash
# Main entry point for the application
python -m webserver.WebServer

# Run with Docker
docker build -t nlweb .
docker run -p 8080:8080 nlweb

# Run startup script (includes data loading)
./startup.sh
```

### Development Setup
```bash
# Check and install dependencies based on your configuration
python check_dependencies.py

# Load data into vector database
python -m tools.db_load <data_file> <site_name>

# Check connectivity to configured services
python -m code.check_connectivity
```

### Testing
```bash
# Run all tests (from code directory)
python -m testing.run_tests --all

# Run specific test types
python -m testing.run_tests --file testing/end_to_end_tests.json --type end_to_end
python -m testing.run_tests --file testing/site_retrieval_tests.json --type site_retrieval
python -m testing.run_tests --file testing/query_retrieval_tests.json --type query_retrieval

# Run single test
python -m testing.run_tests --single --type end_to_end --query "pasta recipes" --show_results

# Quick test scripts
./testing/run_all_tests.sh          # Simple runner
./testing/run_tests_comprehensive.sh --quick  # Comprehensive with options
```

## Architecture

### Core Application Structure
- **`code/`** - Main application code
  - **`webserver/`** - Web server implementation and API endpoints
  - **`core/`** - Core request handling, routing, and business logic
  - **`llm/`** - LLM provider integrations (OpenAI, Anthropic, Gemini, Azure, etc.)
  - **`embedding/`** - Embedding provider implementations
  - **`retrieval/`** - Vector database integrations (Qdrant, Milvus, Azure AI Search, Snowflake)
  - **`pre_retrieval/`** - Query preprocessing (decontextualization, memory, relevance detection)
  - **`prompts/`** - Prompt management and execution
  - **`config/`** - YAML configuration files for all components
  - **`tools/`** - Data loading and utility scripts
  - **`testing/`** - Comprehensive test framework

### Configuration System
The application uses YAML configuration files in `code/config/`:
- `config_llm.yaml` - LLM provider endpoints and settings
- `config_retrieval.yaml` - Vector database configurations  
- `config_embedding.yaml` - Embedding provider settings
- `config_webserver.yaml` - Web server and API settings
- `config_nlweb.yaml` - Core application settings

### Data Flow
1. **Query Processing**: `pre_retrieval/` modules analyze and prepare queries
2. **Retrieval**: `retrieval/` providers search vector databases
3. **LLM Processing**: `llm/` providers generate responses using retrieved context
4. **Response**: Structured JSON responses using Schema.org format

### MCP Integration
NLWeb implements Model Context Protocol (MCP) server functionality:
- Core `ask` method for natural language queries
- Structured responses using Schema.org vocabulary
- Integration with AI assistants and chatbots

### Key Extension Points
- **LLM Providers**: Add new providers in `llm/` following existing patterns
- **Vector Databases**: Extend `retrieval/` with new database integrations  
- **Data Sources**: Use `tools/db_load.py` for custom data ingestion
- **Prompts**: Modify prompts in `prompts/` directory
- **Web UI**: Customize interface in `static/html/`

### Environment Setup
The application requires environment variables for:
- API keys for LLM providers (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- Vector database credentials (varies by provider)
- Configuration paths and runtime settings

Dependencies are automatically installed based on enabled providers when first used, or can be pre-installed using `check_dependencies.py`.