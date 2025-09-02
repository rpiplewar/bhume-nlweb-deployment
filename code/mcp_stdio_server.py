#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
MCP Stdio Server for NLWeb

This script implements a Model Context Protocol (MCP) server that communicates
over stdio (standard input/output) for use with the MCP Inspector tool.
"""

import asyncio
import json
import sys
import logging
import traceback
from typing import Any, Dict
from dotenv import load_dotenv

# Import our existing MCP components
from core.mcp_protocol import (
    MCPRequest, MCPResponse, MCPServerInfo, MCPProtocolError, 
    MCPError, MCPTools, MCPPrompts
)

# Set up logging to stderr so it doesn't interfere with stdout JSON
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

class StdioMCPServer:
    """MCP server that communicates over stdio"""
    
    def __init__(self):
        self.running = True
        
    async def initialize_dependencies(self):
        """Initialize all necessary dependencies"""
        try:
            # Load environment variables
            load_dotenv()
            
            # Initialize router
            import core.router as router
            router.init()
            
            # Initialize LLM providers
            import llm.llm as llm
            llm.init()
            
            # Initialize retrieval clients
            import retrieval.retriever as retriever
            retriever.init()
            
            logger.info("Dependencies initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize dependencies: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a single MCP request"""
        try:
            # Parse the request
            request = MCPRequest(request_data)
            
            logger.info(f"Handling MCP request: {request.method}")
            
            # Check if this is a notification (no response needed)
            is_notification = request.id is None or request.method.startswith("notifications/")
            
            # Route to appropriate handler
            if request.method == "initialize":
                return await self._handle_initialize(request)
            elif request.method == "ping":
                return await self._handle_ping(request)
            elif request.method == "notifications/initialized":
                await self._handle_notifications_initialized_notification(request)
                # For notifications, return None to indicate no response should be sent
                return None
            elif request.method == "tools/list":
                return await self._handle_tools_list(request)
            elif request.method == "tools/call":
                return await self._handle_tools_call(request)
            elif request.method == "prompts/list":
                return await self._handle_prompts_list(request)
            elif request.method == "prompts/get":
                return await self._handle_prompts_get(request)
            elif request.method == "resources/list":
                return await self._handle_resources_list(request)
            else:
                if is_notification:
                    logger.warning(f"Unknown notification: {request.method} - ignoring")
                    return None
                else:
                    logger.warning(f"Unknown method: {request.method}")
                    return MCPResponse.error(
                        MCPError.METHOD_NOT_FOUND,
                        f"Unknown method: {request.method}",
                        request.id,
                        legacy_format=request.is_legacy
                    )
                
        except MCPProtocolError as e:
            logger.error(f"MCP protocol error: {e}")
            return MCPResponse.error(e.code, e.message, None, e.data)
            
        except Exception as e:
            logger.error(f"Unexpected error in handle_request: {e}")
            logger.error(traceback.format_exc())
            return MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                f"Internal server error: {str(e)}",
                None
            )
    
    async def _handle_ping(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle ping method"""
        logger.info("Handling ping request")
        return MCPResponse.success({}, request.id, request.is_legacy)
    
    async def _handle_notifications_initialized(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle notifications/initialized method"""
        logger.info("Handling notifications/initialized - client is ready")
        # For notifications, we typically don't send a response back
        # But our current architecture expects a response, so return empty success
        return MCPResponse.success({}, request.id, request.is_legacy)
    
    async def _handle_notifications_initialized_notification(self, request: MCPRequest) -> None:
        """Handle notifications/initialized notification (no response needed)"""
        logger.info("Client initialization complete - ready for requests")
        # This is a notification, so no response is needed
    
    async def _handle_initialize(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP initialize method"""
        try:
            client_capabilities = request.params.get("capabilities", {})
            protocol_version = request.params.get("protocolVersion", "2024-11-05")
            
            logger.info(f"Initialize: version={protocol_version}")
            
            server_capabilities = MCPServerInfo.get_capabilities()
            
            result = {
                "protocolVersion": protocol_version,
                "capabilities": server_capabilities["capabilities"],
                "serverInfo": server_capabilities["serverInfo"]
            }
            
            return MCPResponse.success(result, request.id, request.is_legacy)
        except Exception as e:
            logger.error(f"Error in _handle_initialize: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _handle_tools_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle tools/list method"""
        try:
            logger.info("Handling tools/list request")
            tools = MCPTools.get_tool_list()
            result = {"tools": tools}
            return MCPResponse.success(result, request.id, request.is_legacy)
        except Exception as e:
            logger.error(f"Error in _handle_tools_list: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _handle_tools_call(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle tools/call method"""
        try:
            tool_name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            
            logger.info(f"Calling tool: {tool_name} with args: {arguments}")
            
            if tool_name in ["ask_nlw", "search", "query"]:
                # Call the core function directly
                query = arguments.get("query", "")
                site = arguments.get("site", "all")
                
                if not query:
                    return MCPResponse.error(
                        MCPError.INVALID_PARAMS,
                        "Missing required parameter: query",
                        request.id,
                        legacy_format=request.is_legacy
                    )
                
                # For now, return a mock response since we need to adapt the handler
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Tool call: {tool_name}\nQuery: {query}\nSite: {site}\n\nNote: This is a mock response from the stdio MCP server. The full implementation would perform the actual search."
                        }
                    ]
                }
                
                return MCPResponse.success(result, request.id, request.is_legacy)
                
            elif tool_name == "get_sites":
                from config.config import CONFIG
                sites = CONFIG.get_allowed_sites()
                result = {
                    "content": [
                        {
                            "type": "text", 
                            "text": f"Available sites: {', '.join(sites)}"
                        }
                    ]
                }
                return MCPResponse.success(result, request.id, request.is_legacy)
            
            else:
                return MCPResponse.error(
                    MCPError.TOOL_NOT_FOUND,
                    f"Tool not found: {tool_name}",
                    request.id,
                    legacy_format=request.is_legacy
                )
                
        except Exception as e:
            logger.error(f"Tool call error: {e}")
            logger.error(traceback.format_exc())
            return MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                f"Tool execution failed: {str(e)}",
                request.id,
                legacy_format=request.is_legacy
            )
    
    async def _handle_prompts_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle prompts/list method"""
        try:
            logger.info("Handling prompts/list request")
            prompts = MCPPrompts.get_prompt_list()
            result = {"prompts": prompts}
            return MCPResponse.success(result, request.id, request.is_legacy)
        except Exception as e:
            logger.error(f"Error in _handle_prompts_list: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _handle_prompts_get(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle prompts/get method"""
        try:
            prompt_name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            
            if not prompt_name:
                return MCPResponse.error(
                    MCPError.INVALID_PARAMS,
                    "Missing required parameter: name",
                    request.id,
                    legacy_format=request.is_legacy
                )
            
            prompt = MCPPrompts.get_prompt(prompt_name, arguments)
            
            if not prompt:
                return MCPResponse.error(
                    MCPError.PROMPT_NOT_FOUND,
                    f"Prompt not found: {prompt_name}",
                    request.id,
                    legacy_format=request.is_legacy
                )
            
            return MCPResponse.success(prompt, request.id, request.is_legacy)
        except Exception as e:
            logger.error(f"Error in _handle_prompts_get: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def _handle_resources_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle resources/list method"""
        try:
            logger.info("Handling resources/list request")
            from config.config import CONFIG
            sites = CONFIG.get_allowed_sites()
            
            resources = []
            for site in sites:
                resources.append({
                    "uri": f"nlweb://site/{site}",
                    "name": site,
                    "description": f"NLWeb site: {site}",
                    "mimeType": "application/json"
                })
            
            result = {"resources": resources}
            return MCPResponse.success(result, request.id, request.is_legacy)
        except Exception as e:
            logger.error(f"Error in _handle_resources_list: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def run(self):
        """Main server loop"""
        try:
            # Initialize dependencies
            await self.initialize_dependencies()
            
            logger.info("NLWeb MCP Stdio Server starting...")
            
            # Send server info to stderr for debugging
            server_info = MCPServerInfo.get_server_info()
            print(f"Server: {server_info['server']} v{server_info['version']}", file=sys.stderr)
            print(f"Available tools: {len(server_info['tools'])}", file=sys.stderr)
            print("Server ready to accept requests", file=sys.stderr)
            
            # Create async stdin reader
            loop = asyncio.get_event_loop()
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            
            while self.running:
                try:
                    # Read from stdin asynchronously
                    line_bytes = await reader.readline()
                    if not line_bytes:
                        logger.info("EOF received, stopping server")
                        break
                    
                    line = line_bytes.decode('utf-8').strip()
                    if not line:
                        continue
                    
                    logger.info(f"Received request: {line[:100]}...")
                    
                    # Parse JSON request
                    try:
                        request_data = json.loads(line)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON: {e}")
                        error_response = MCPResponse.error(
                            MCPError.PARSE_ERROR,
                            f"Invalid JSON: {str(e)}"
                        )
                        response_json = json.dumps(error_response)
                        print(response_json, flush=True)
                        logger.info(f"Sent error response: {response_json}")
                        continue
                    
                    # Handle the request
                    response = await self.handle_request(request_data)
                    
                    # Send response to stdout (only if there is a response)
                    if response is not None:
                        response_json = json.dumps(response)
                        print(response_json, flush=True)
                        logger.info(f"Sent response: {response_json[:200]}...")
                    else:
                        logger.info("No response needed (notification)")
                    
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    logger.error(traceback.format_exc())
                    try:
                        error_response = MCPResponse.error(
                            MCPError.INTERNAL_ERROR,
                            f"Server error: {str(e)}"
                        )
                        response_json = json.dumps(error_response)
                        print(response_json, flush=True)
                        logger.info(f"Sent error response: {response_json}")
                    except Exception as send_error:
                        logger.error(f"Failed to send error response: {send_error}")
                    # Don't break the loop, continue processing
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)
        
        logger.info("NLWeb MCP Stdio Server stopped")

async def main():
    """Main entry point"""
    server = StdioMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main()) 