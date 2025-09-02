# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
MCP Router for NLWeb

This module routes MCP requests to appropriate handlers based on the method
and maintains backward compatibility with existing function_call format.
"""

import json
import asyncio
import traceback
from typing import Dict, Any, Optional, Callable
from utils.logger import get_logger
from core.mcp_protocol import (
    MCPRequest, MCPResponse, MCPServerInfo, MCPProtocolError, 
    MCPError, MCPTools, MCPPrompts, format_sse_message
)
from core.mcp_handler import (
    handle_ask_function, handle_list_tools_function, 
    handle_list_prompts_function, handle_get_prompt_function,
    handle_get_sites_function, handle_site_parameter
)

logger = get_logger(__name__)

class MCPRouter:
    """Routes MCP requests to appropriate handlers"""
    
    def __init__(self):
        self.method_handlers = {
            # Core MCP methods
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            
            # Legacy compatibility methods
            "list_tools": self._handle_tools_list,
            "list_prompts": self._handle_prompts_list,
            "get_prompt": self._handle_prompts_get,
            "get_sites": self._handle_resources_list,
        }
    
    async def route_request(self, query_params: Dict, body: bytes, 
                          send_response: Callable, send_chunk: Callable, 
                          streaming: bool = False) -> None:
        """Route MCP request to appropriate handler"""
        try:
            # Parse the request
            request = MCPRequest(body)
            
            logger.info(f"MCP request: method={request.method}, legacy={request.is_legacy}")
            
            # Route to appropriate handler
            if request.method in self.method_handlers:
                await self.method_handlers[request.method](
                    request, query_params, send_response, send_chunk, streaming
                )
            else:
                # Unknown method
                error_response = MCPResponse.error(
                    MCPError.METHOD_NOT_FOUND,
                    f"Unknown method: {request.method}",
                    request.id,
                    legacy_format=request.is_legacy
                )
                
                await send_response(404, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(error_response), end_response=True)
                
        except MCPProtocolError as e:
            logger.error(f"MCP protocol error: {e}")
            error_response = MCPResponse.error(
                e.code, e.message, None, e.data, legacy_format=False
            )
            await send_response(400, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
            
        except Exception as e:
            logger.error(f"MCP router error: {e}\n{traceback.format_exc()}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                f"Internal server error: {str(e)}",
                None,
                legacy_format=False
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
    
    async def _handle_initialize(self, request: MCPRequest, query_params: Dict,
                                send_response: Callable, send_chunk: Callable, 
                                streaming: bool) -> None:
        """Handle MCP initialize method"""
        try:
            # Client capabilities (from request params)
            client_capabilities = request.params.get("capabilities", {})
            protocol_version = request.params.get("protocolVersion", "2024-11-05")
            
            logger.info(f"MCP initialize: version={protocol_version}, capabilities={client_capabilities}")
            
            # Server capabilities
            server_capabilities = MCPServerInfo.get_capabilities()
            
            result = {
                "protocolVersion": protocol_version,
                "capabilities": server_capabilities["capabilities"],
                "serverInfo": server_capabilities["serverInfo"]
            }
            
            response = MCPResponse.success(result, request.id, request.is_legacy)
            
            await send_response(200, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(response), end_response=True)
            
        except Exception as e:
            logger.error(f"Initialize error: {e}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                str(e),
                request.id,
                legacy_format=request.is_legacy
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
    
    async def _handle_tools_list(self, request: MCPRequest, query_params: Dict,
                                send_response: Callable, send_chunk: Callable,
                                streaming: bool) -> None:
        """Handle tools/list method"""
        try:
            if request.is_legacy:
                # Use existing handler for backward compatibility
                await handle_list_tools_function(send_response, send_chunk)
            else:
                # New JSON-RPC format
                tools = MCPTools.get_tool_list()
                result = {"tools": tools}
                
                response = MCPResponse.success(result, request.id)
                
                await send_response(200, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(response), end_response=True)
                
        except Exception as e:
            logger.error(f"Tools list error: {e}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                str(e),
                request.id,
                legacy_format=request.is_legacy
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
    
    async def _handle_tools_call(self, request: MCPRequest, query_params: Dict,
                                send_response: Callable, send_chunk: Callable,
                                streaming: bool) -> None:
        """Handle tools/call method"""
        try:
            if request.is_legacy:
                # Use existing handler for backward compatibility
                await handle_ask_function(
                    request.function_call, query_params, 
                    send_response, send_chunk, streaming
                )
            else:
                # New JSON-RPC format
                tool_name = request.params.get("name")
                arguments = request.params.get("arguments", {})
                
                # Create function_call structure for existing handler
                function_call = {
                    "name": tool_name,
                    "arguments": json.dumps(arguments) if isinstance(arguments, dict) else arguments
                }
                
                # Check if streaming was requested in arguments
                if isinstance(arguments, dict) and arguments.get("streaming", False):
                    streaming = True
                
                if streaming:
                    # For streaming, we need to handle the response differently
                    await self._handle_streaming_tool_call(
                        function_call, request, query_params, send_response, send_chunk
                    )
                else:
                    # Use existing handler for non-streaming
                    await handle_ask_function(
                        function_call, query_params, 
                        send_response, send_chunk, streaming
                    )
                
        except Exception as e:
            logger.error(f"Tools call error: {e}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                str(e),
                request.id,
                legacy_format=request.is_legacy
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
    
    async def _handle_streaming_tool_call(self, function_call: Dict, request: MCPRequest,
                                        query_params: Dict, send_response: Callable,
                                        send_chunk: Callable) -> None:
        """Handle streaming tool calls with proper JSON-RPC format"""
        try:
            # Set up SSE headers
            response_headers = {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
            
            await send_response(200, response_headers)
            
            # Send initial message
            initial_message = format_sse_message({
                "jsonrpc": "2.0",
                "method": "tools/call_progress",
                "params": {
                    "id": request.id,
                    "status": "started"
                }
            })
            await send_chunk(initial_message, end_response=False)
            
            # Custom chunk wrapper for JSON-RPC streaming
            async def jsonrpc_send_chunk(data, end_response=False):
                if isinstance(data, str) and data.startswith("data: "):
                    # Already formatted, just send
                    await send_chunk(data, end_response=end_response)
                else:
                    # Format as JSON-RPC progress
                    progress_message = format_sse_message({
                        "jsonrpc": "2.0", 
                        "method": "tools/call_progress",
                        "params": {
                            "id": request.id,
                            "data": data
                        }
                    })
                    await send_chunk(progress_message, end_response=end_response)
            
            # Use existing handler with custom wrapper
            await handle_ask_function(
                function_call, query_params,
                send_response, jsonrpc_send_chunk, streaming=True
            )
            
            # Send completion message
            completion_message = format_sse_message({
                "jsonrpc": "2.0",
                "method": "tools/call_complete", 
                "params": {
                    "id": request.id,
                    "status": "completed"
                }
            })
            await send_chunk(completion_message, end_response=True)
            
        except Exception as e:
            logger.error(f"Streaming tool call error: {e}")
            # Send error via SSE
            error_message = format_sse_message({
                "jsonrpc": "2.0",
                "error": {
                    "code": MCPError.INTERNAL_ERROR,
                    "message": str(e)
                },
                "id": request.id
            })
            await send_chunk(error_message, end_response=True)
    
    async def _handle_prompts_list(self, request: MCPRequest, query_params: Dict,
                                  send_response: Callable, send_chunk: Callable,
                                  streaming: bool) -> None:
        """Handle prompts/list method"""
        try:
            if request.is_legacy:
                await handle_list_prompts_function(send_response, send_chunk)
            else:
                prompts = MCPPrompts.get_prompt_list()
                result = {"prompts": prompts}
                
                response = MCPResponse.success(result, request.id)
                
                await send_response(200, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(response), end_response=True)
                
        except Exception as e:
            logger.error(f"Prompts list error: {e}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                str(e),
                request.id,
                legacy_format=request.is_legacy
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
    
    async def _handle_prompts_get(self, request: MCPRequest, query_params: Dict,
                                 send_response: Callable, send_chunk: Callable,
                                 streaming: bool) -> None:
        """Handle prompts/get method"""
        try:
            if request.is_legacy:
                await handle_get_prompt_function(
                    request.function_call, send_response, send_chunk
                )
            else:
                prompt_name = request.params.get("name")
                arguments = request.params.get("arguments", {})
                
                if not prompt_name:
                    error_response = MCPResponse.error(
                        MCPError.INVALID_PARAMS,
                        "Missing required parameter: name",
                        request.id
                    )
                    await send_response(400, {'Content-Type': 'application/json'})
                    await send_chunk(json.dumps(error_response), end_response=True)
                    return
                
                prompt = MCPPrompts.get_prompt(prompt_name, arguments)
                
                if not prompt:
                    error_response = MCPResponse.error(
                        MCPError.PROMPT_NOT_FOUND,
                        f"Prompt not found: {prompt_name}",
                        request.id
                    )
                    await send_response(404, {'Content-Type': 'application/json'})
                    await send_chunk(json.dumps(error_response), end_response=True)
                    return
                
                response = MCPResponse.success(prompt, request.id)
                
                await send_response(200, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(response), end_response=True)
                
        except Exception as e:
            logger.error(f"Prompts get error: {e}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                str(e),
                request.id,
                legacy_format=request.is_legacy
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
    
    async def _handle_resources_list(self, request: MCPRequest, query_params: Dict,
                                   send_response: Callable, send_chunk: Callable,
                                   streaming: bool) -> None:
        """Handle resources/list method (sites)"""
        try:
            if request.is_legacy:
                await handle_get_sites_function(send_response, send_chunk)
            else:
                # For now, resources are the sites
                from core.mcp_handler import handle_get_sites_function
                
                # Capture the response from the legacy handler
                responses = []
                
                async def capture_response(code, headers):
                    pass
                
                async def capture_chunk(data, end_response=False):
                    if isinstance(data, (str, bytes)):
                        try:
                            if isinstance(data, bytes):
                                data = data.decode('utf-8')
                            response_data = json.loads(data)
                            responses.append(response_data)
                        except:
                            pass
                
                await handle_get_sites_function(capture_response, capture_chunk)
                
                # Convert to MCP format
                if responses and "response" in responses[0]:
                    sites = responses[0]["response"].get("sites", [])
                    
                    # Convert sites to MCP resource format
                    resources = []
                    for site in sites:
                        resources.append({
                            "uri": f"nlweb://site/{site['id']}",
                            "name": site["name"],
                            "description": site.get("description", f"Site: {site['name']}"),
                            "mimeType": "application/json"
                        })
                    
                    result = {"resources": resources}
                else:
                    result = {"resources": []}
                
                response = MCPResponse.success(result, request.id)
                
                await send_response(200, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(response), end_response=True)
                
        except Exception as e:
            logger.error(f"Resources list error: {e}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                str(e),
                request.id,
                legacy_format=request.is_legacy
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)
    
    async def _handle_resources_read(self, request: MCPRequest, query_params: Dict,
                                   send_response: Callable, send_chunk: Callable,
                                   streaming: bool) -> None:
        """Handle resources/read method"""
        try:
            uri = request.params.get("uri")
            
            if not uri:
                error_response = MCPResponse.error(
                    MCPError.INVALID_PARAMS,
                    "Missing required parameter: uri",
                    request.id
                )
                await send_response(400, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(error_response), end_response=True)
                return
            
            # For now, just return basic info about the resource
            if uri.startswith("nlweb://site/"):
                site_id = uri.replace("nlweb://site/", "")
                result = {
                    "contents": [{
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "site_id": site_id,
                            "type": "site_info",
                            "description": f"Information about site: {site_id}"
                        }, indent=2)
                    }]
                }
            else:
                error_response = MCPResponse.error(
                    MCPError.RESOURCE_NOT_FOUND,
                    f"Resource not found: {uri}",
                    request.id
                )
                await send_response(404, {'Content-Type': 'application/json'})
                await send_chunk(json.dumps(error_response), end_response=True)
                return
            
            response = MCPResponse.success(result, request.id)
            
            await send_response(200, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(response), end_response=True)
            
        except Exception as e:
            logger.error(f"Resources read error: {e}")
            error_response = MCPResponse.error(
                MCPError.INTERNAL_ERROR,
                str(e),
                request.id,
                legacy_format=request.is_legacy
            )
            await send_response(500, {'Content-Type': 'application/json'})
            await send_chunk(json.dumps(error_response), end_response=True)

# Global router instance
mcp_router = MCPRouter() 