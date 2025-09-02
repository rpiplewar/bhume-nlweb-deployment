# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
MCP Protocol Implementation for NLWeb

This module implements the Model Context Protocol (MCP) with JSON-RPC 2.0 support
for Claude Desktop and Web integration, while maintaining backward compatibility
with the existing function_call format.
"""

import json
import time
import uuid
from typing import Dict, Any, Optional, List, Union
from utils.logger import get_logger
from config.config import CONFIG

logger = get_logger(__name__)

# MCP Protocol Version Support
SUPPORTED_PROTOCOL_VERSIONS = ["2024-11-05", "2025-03-26"]
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

class MCPError:
    """Standard MCP error codes"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP-specific errors
    TOOL_NOT_FOUND = -32001
    RESOURCE_NOT_FOUND = -32002
    PROMPT_NOT_FOUND = -32003

class MCPServerInfo:
    """Server information and capabilities for MCP discovery"""
    
    @staticmethod
    def get_server_info() -> Dict[str, Any]:
        """Return server information for GET /mcp requests"""
        allowed_sites = CONFIG.get_allowed_sites()
        
        return {
            "server": "nlweb-mcp-server",
            "version": "1.0.0",
            "description": "NLWeb MCP server for AI-powered search and retrieval across multiple data sources",
            "usage": "This endpoint implements the Model Context Protocol (MCP). Use POST with JSON-RPC 2.0 requests.",
            "documentation": "/mcp-docs",
            "protocol_version": DEFAULT_PROTOCOL_VERSION,
            "supported_versions": SUPPORTED_PROTOCOL_VERSIONS,
            "transport": ["http", "sse"],
            "capabilities": {
                "tools": True,
                "prompts": True,
                "resources": True,
                "sampling": False,
                "experimental": {
                    "streaming": True
                }
            },
            "tools": {
                "ask_nlw": "Search and retrieve information from configured data sources",
                "search": "Alias for ask_nlw - search across all or specific sites",
                "query": "Alias for ask_nlw - query specific information",
                "get_sites": "Get list of available sites/data sources",
                "list_tools": "List all available tools",
                "list_prompts": "List available prompts",
                "get_prompt": "Get a specific prompt by ID"
            },
            "sites": allowed_sites,
            "endpoints": {
                "main": "/mcp",
                "sse": "/mcp/sse", 
                "health": "/mcp/health",
                "capabilities": "/mcp/capabilities"
            },
            "example": {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "ask_nlw",
                    "arguments": {
                        "query": "example search query",
                        "site": "all"
                    }
                },
                "id": 1
            },
            "legacy_format": {
                "function_call": {
                    "name": "ask_nlw",
                    "arguments": "{\"query\": \"example search query\", \"site\": \"all\"}"
                }
            }
        }
    
    @staticmethod 
    def get_capabilities() -> Dict[str, Any]:
        """Return detailed capability information"""
        return {
            "protocolVersion": DEFAULT_PROTOCOL_VERSION,
            "capabilities": {
                "experimental": {},
                "sampling": {},
                "tools": {
                    "listChanged": True
                },
                "prompts": {
                    "listChanged": True  
                },
                "resources": {
                    "subscribe": False,
                    "listChanged": True
                },
                "logging": {}
            },
            "serverInfo": {
                "name": "nlweb-mcp-server",
                "version": "1.0.0"
            }
        }

class MCPRequest:
    """Parse and validate MCP requests"""
    
    def __init__(self, raw_data: Union[str, bytes, Dict]):
        self.raw_data = raw_data
        self.is_jsonrpc = False
        self.is_legacy = False
        self.method = None
        self.params = None
        self.id = None
        self.function_call = None
        
        self._parse()
    
    def _parse(self):
        """Parse the request and determine format"""
        try:
            if isinstance(self.raw_data, (str, bytes)):
                data = json.loads(self.raw_data)
            else:
                data = self.raw_data
                
            # Check for JSON-RPC 2.0 format
            if "jsonrpc" in data and data["jsonrpc"] == "2.0":
                self.is_jsonrpc = True
                self.method = data.get("method")
                self.params = data.get("params", {})
                self.id = data.get("id")
                
            # Check for legacy function_call format
            elif "function_call" in data:
                self.is_legacy = True
                self.function_call = data["function_call"]
                
                # Convert legacy format to standard format
                self.method = self._legacy_to_method(self.function_call.get("name"))
                self.params = self._parse_legacy_arguments(self.function_call.get("arguments", "{}"))
                self.id = str(uuid.uuid4())  # Generate ID for legacy requests
                
            else:
                raise ValueError("Unknown request format")
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse MCP request: {e}")
            raise MCPProtocolError(
                MCPError.PARSE_ERROR,
                f"Invalid request format: {str(e)}",
                data={"raw_data": str(self.raw_data)[:200]}
            )
    
    def _legacy_to_method(self, function_name: str) -> str:
        """Convert legacy function names to MCP method names"""
        method_mapping = {
            "ask": "tools/call",
            "ask_nlw": "tools/call", 
            "query": "tools/call",
            "search": "tools/call",
            "list_tools": "tools/list",
            "list_prompts": "prompts/list",
            "get_prompt": "prompts/get",
            "get_sites": "resources/list"
        }
        
        method = method_mapping.get(function_name, "tools/call")
        
        # Store original function name for backward compatibility
        if method == "tools/call":
            self._original_tool_name = function_name
            
        return method
    
    def _parse_legacy_arguments(self, arguments: str) -> Dict[str, Any]:
        """Parse legacy arguments string to dictionary"""
        try:
            if isinstance(arguments, str):
                args = json.loads(arguments)
            else:
                args = arguments
                
            # For tool calls, wrap arguments properly
            if hasattr(self, '_original_tool_name'):
                return {
                    "name": self._original_tool_name,
                    "arguments": args
                }
            
            return args
            
        except (json.JSONDecodeError, TypeError):
            # If not valid JSON, treat as simple string query
            return {"query": str(arguments)}

class MCPResponse:
    """Format MCP responses according to protocol"""
    
    @staticmethod
    def success(result: Any, request_id: Any = None, legacy_format: bool = False) -> Dict[str, Any]:
        """Create successful response"""
        if legacy_format:
            return {
                "type": "function_response",
                "status": "success", 
                "response": result
            }
        else:
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
    
    @staticmethod
    def error(code: int, message: str, request_id: Any = None, 
              data: Any = None, legacy_format: bool = False) -> Dict[str, Any]:
        """Create error response"""
        if legacy_format:
            return {
                "type": "function_response",
                "status": "error",
                "error": message
            }
        else:
            error_obj = {
                "code": code,
                "message": message
            }
            if data is not None:
                error_obj["data"] = data
                
            return {
                "jsonrpc": "2.0", 
                "error": error_obj,
                "id": request_id
            }

class MCPProtocolError(Exception):
    """MCP protocol-specific errors"""
    
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

class MCPTools:
    """Tool definitions and metadata for MCP"""
    
    @staticmethod
    def get_tool_list() -> List[Dict[str, Any]]:
        """Return list of available tools"""
        allowed_sites = CONFIG.get_allowed_sites()
        site_enum = allowed_sites + ["all"]
        
        return [
            {
                "name": "ask_nlw",
                "description": "Search and retrieve information from NLWeb data sources. Supports natural language queries across multiple sites including recipes, movies, research papers, and more.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query"
                        },
                        "site": {
                            "type": "string", 
                            "enum": site_enum,
                            "description": "Specific site to search, or 'all' for all sites",
                            "default": "all"
                        },
                        "prev_query": {
                            "type": "string",
                            "description": "Previous query for context (optional)"
                        },
                        "context_url": {
                            "type": "string",
                            "description": "URL for additional context (optional)" 
                        },
                        "streaming": {
                            "type": "boolean",
                            "description": "Enable streaming response",
                            "default": False
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_sites", 
                "description": "Get list of available sites/data sources that can be searched",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "search",
                "description": "Alias for ask_nlw - search across data sources", 
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "site": {
                            "type": "string",
                            "enum": site_enum, 
                            "default": "all"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "query",
                "description": "Alias for ask_nlw - query specific information",
                "inputSchema": {
                    "type": "object", 
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Information query"
                        },
                        "site": {
                            "type": "string",
                            "enum": site_enum,
                            "default": "all" 
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

class MCPPrompts:
    """Prompt definitions for MCP"""
    
    @staticmethod
    def get_prompt_list() -> List[Dict[str, Any]]:
        """Return list of available prompts"""
        return [
            {
                "name": "search_assistant",
                "description": "A helpful assistant for searching and retrieving information",
                "arguments": [
                    {
                        "name": "domain",
                        "description": "The domain or topic area to focus on",
                        "required": False
                    }
                ]
            },
            {
                "name": "research_helper", 
                "description": "An assistant specialized in research and academic queries",
                "arguments": [
                    {
                        "name": "field", 
                        "description": "Research field or academic discipline",
                        "required": False
                    }
                ]
            },
            {
                "name": "recipe_finder",
                "description": "A culinary assistant for finding and exploring recipes",
                "arguments": [
                    {
                        "name": "cuisine",
                        "description": "Type of cuisine or cooking style",
                        "required": False
                    }
                ]
            }
        ]
    
    @staticmethod
    def get_prompt(name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get a specific prompt with arguments"""
        arguments = arguments or {}
        
        prompts = {
            "search_assistant": {
                "name": "search_assistant",
                "description": "A helpful assistant for searching and retrieving information",
                "messages": [
                    {
                        "role": "system",
                        "content": {
                            "type": "text",
                            "text": f"You are a helpful search assistant specializing in {arguments.get('domain', 'general information')}. Use the available search tools to find accurate, relevant information and present it clearly to users."
                        }
                    }
                ]
            },
            "research_helper": {
                "name": "research_helper", 
                "description": "An assistant specialized in research and academic queries",
                "messages": [
                    {
                        "role": "system",
                        "content": {
                            "type": "text", 
                            "text": f"You are a research assistant with expertise in {arguments.get('field', 'academic research')}. Help users find scholarly information, research papers, and academic resources. Always cite sources and provide context for your findings."
                        }
                    }
                ]
            },
            "recipe_finder": {
                "name": "recipe_finder",
                "description": "A culinary assistant for finding and exploring recipes", 
                "messages": [
                    {
                        "role": "system",
                        "content": {
                            "type": "text",
                            "text": f"You are a culinary assistant specializing in {arguments.get('cuisine', 'international cuisine')}. Help users find recipes, cooking techniques, and culinary information. Provide clear instructions and helpful cooking tips."
                        }
                    }
                ]
            }
        }
        
        return prompts.get(name, {})

def format_sse_message(data: Dict[str, Any], event_type: str = "message") -> str:
    """Format data as Server-Sent Event message"""
    lines = []
    if event_type:
        lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")  # Empty line to end the event
    return "\n".join(lines) + "\n" 