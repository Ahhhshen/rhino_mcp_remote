import { McpAgent } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { RhinoTools } from "./rhino-tools";

// Export the Env interface
export interface Env {
  RHINO_WS: DurableObjectNamespace;
}

// 1. Define MCP Agent
export class RhinoMCP extends McpAgent {
  server = new McpServer({
    name: "Rhino MCP",
    version: "1.0.0",
  });

  async init() {
    new RhinoTools(this.server);
  }
}

// --- WebSocket <-> Rhino tool integration ---
export class RhinoWebSocket {
  private state: DurableObjectState;
  private rhinoSocket: WebSocket | null = null;
  private requestId = 0;
  private pending: Record<number, (resp: any) => void> = {};

  constructor(state: DurableObjectState) {
    this.state = state;
  }

  async fetch(request: Request) {
    const url = new URL(request.url);

    // WebSocket 升级
    if (request.headers.get("upgrade") === "websocket") {
      const { 0: client, 1: server } = new WebSocketPair();
      server.accept();
      this.rhinoSocket = server;

      if (server.readyState !== WebSocket.OPEN) {
        return new Response("WebSocket connection failed", { status: 500 });
      }

      server.addEventListener("message", async (event) => {
        try {
          const data = event.data;
          const message =
            typeof data === "string" ? data : new TextDecoder().decode(data);
          console.log("Received message:", message);

          const msg = JSON.parse(message);
          if (msg.id && this.pending[msg.id]) {
            this.pending[msg.id](msg);
            delete this.pending[msg.id];
          } else {
            console.log("Unknown message received:", msg);
            server.send(
              JSON.stringify({
                status: "error",
                message: "Unknown or unsolicited message",
              })
            );
          }
        } catch (e) {
          console.error("Error processing message:", e);
          server.send(
            JSON.stringify({
              status: "error",
              message: String(e),
            })
          );
        }
      });

      server.addEventListener("close", () => {
        console.log("WebSocket connection closed");
        this.rhinoSocket = null;
      });

      server.addEventListener("error", (error) => {
        console.error("WebSocket error:", error);
      });

      return new Response(null, {
        status: 101,
        webSocket: client,
        headers: {
          Upgrade: "websocket",
          Connection: "Upgrade",
        },
      });
    }

    // 处理 HTTP POST /send-command
    if (request.method === "POST" && url.pathname === "/send-command") {
      const body = (await request.json()) as { type: string; params?: any };
      const { type, params } = body;

      // 生成唯一请求ID
      const id = ++this.requestId;

      // 通过 WebSocket 发给 Rhino
      if (!this.rhinoSocket || this.rhinoSocket.readyState !== WebSocket.OPEN) {
        return new Response(
          JSON.stringify({
            status: "error",
            message: "No Rhino WebSocket client connected",
          }),
          { status: 503 }
        );
      }

      this.rhinoSocket.send(JSON.stringify({ id, type, params }));

      // 等待 Rhino 返回
      const result = await new Promise((resolve, reject) => {
        this.pending[id] = resolve;
        setTimeout(() => {
          if (this.pending[id]) {
            delete this.pending[id];
            reject(new Error("Timeout waiting for Rhino response"));
          }
        }, 30000);
      });

      return new Response(JSON.stringify(result), { status: 200 });
    }

    return new Response("Not found", { status: 404 });
  }

  async sendRhinoCommand(commandType: string, params?: any): Promise<any> {
    if (!this.rhinoSocket || this.rhinoSocket.readyState !== 1) {
      throw new Error("No Rhino WebSocket client connected");
    }
    return new Promise((resolve, reject) => {
      const id = ++this.requestId;
      this.pending[id] = resolve;
      const payload = { id, type: commandType, params };
      if (this.rhinoSocket) {
        this.rhinoSocket.send(JSON.stringify(payload));
      }
      setTimeout(() => {
        if (this.pending[id]) {
          delete this.pending[id];
          reject(new Error("Timeout waiting for Rhino response"));
        }
      }, 30000);
    });
  }
}

// Export the Durable Object class
export { RhinoWebSocket as RhinoWebSocketDO };

export default {
  fetch(request: Request, env: Env, ctx: ExecutionContext) {
    const url = new URL(request.url);

    // 1. WebSocket upgrade support
    if (request.headers.get("upgrade") === "websocket") {
      const id = env.RHINO_WS.idFromName("rhino");
      const obj = env.RHINO_WS.get(id);
      return obj.fetch(request);
    }

    // 2. Original HTTP/SSE MCP server routes
    if (url.pathname === "/sse" || url.pathname === "/sse/message") {
      // @ts-ignore
      return RhinoMCP.serveSSE("/sse").fetch(request, env, ctx);
    }

    if (url.pathname === "/mcp") {
      // @ts-ignore
      return RhinoMCP.serve("/mcp").fetch(request, env, ctx);
    }

    return new Response("Not found", { status: 404 });
  },
};

// Add sendRhinoCommand function to forward commands through DO
export async function sendRhinoCommand(
  env: Env,
  commandType: string,
  params?: any
): Promise<any> {
  const id = env.RHINO_WS.idFromName("rhino");
  const obj = env.RHINO_WS.get(id);
  const resp = await obj.fetch("https://dummy/send-command", {
    method: "POST",
    body: JSON.stringify({ type: commandType, params }),
  });
  return await resp.json();
}
