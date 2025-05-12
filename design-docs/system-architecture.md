# RhinoMCP Remote: System Architecture

## Overview

RhinoMCP Remote is a cloud-hosted implementation of the Model Context Protocol (MCP) for Rhino. This system allows Reer's web application to communicate with multiple users' local Rhino instances via a centralized Cloudflare-hosted infrastructure, enabling remote control and data exchange between LLMs (like Claude) and Rhino.

## System Components

### 1. Local Rhino Plugin

- **Modified `rhino_script.py`**: An adaptation of the original MCP plugin that connects outbound to the cloud service
- **Authentication Module**: Manages user authentication and maintains secure connection
- **WebSocket Client**: Establishes and maintains persistent outbound connection to the remote server
- **Command Executor**: Processes incoming commands and returns results

### 2. Cloudflare Remote MCP Server

- **Connection Manager**: Manages WebSocket connections from multiple Rhino instances
- **Durable Objects**: Maintains stateful connections for each user
- **Authentication Service**: Validates connections from both Rhino plugins and web application
- **Command Router**: Routes commands from web application to correct Rhino instance
- **Response Handler**: Routes responses from Rhino instances back to web application

### 3. Web Application Integration

- **MCP Client**: Implements the MCP protocol for communication with the Remote MCP Server
- **User Management**: Associates web application users with their Rhino connections
- **UI Components**: Provides interface for users to initiate/check connection status
- **Command Interface**: Allows sending commands to user's Rhino instance

## Data Flow

### Connection Establishment

1. User authenticates in web application and receives unique connection parameters (URL and token)
2. User configures local Rhino plugin with these parameters
3. Rhino plugin initiates outbound WebSocket connection to Cloudflare server
4. Cloudflare server authenticates connection and associates it with user account
5. Web application receives notification that the user's Rhino is connected

### Command Execution

1. Web application or LLM initiates a command (with user ID) to the Remote MCP Server
2. Remote MCP Server looks up the associated WebSocket connection for that user
3. Command is forwarded to the specific Rhino instance over the established WebSocket
4. Rhino instance executes the command locally
5. Results are sent back over the same WebSocket connection
6. Remote MCP Server routes results back to the originating web application or LLM

## Security Considerations

- All connections use secure WebSockets (WSS)
- User authentication required for both plugin and web application connections
- Rate limiting to prevent abuse
- Command validation before execution
- Sanitization of data received from Rhino instances

## Scalability

The architecture is designed for horizontal scaling:

- Cloudflare Workers provide global distribution and auto-scaling
- Durable Objects maintain state for persistent connections
- Connection pooling allows efficient management of many simultaneous users

## Failure Handling

- Automatic reconnection logic in Rhino plugin if connection is lost
- Heartbeat mechanism to detect stale connections
- Graceful degradation when services are unavailable
- Clear error messaging for both end users and developers 