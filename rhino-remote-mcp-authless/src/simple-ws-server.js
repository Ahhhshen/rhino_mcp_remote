const WebSocket = require("ws");
const wss = new WebSocket.Server({ port: 8787 });

wss.on("connection", function connection(ws) {
  console.log("Client connected");

  // 主动发一个有效的 Rhino 命令
  ws.send(JSON.stringify({ type: "get_rhino_layers", id: 1 }));

  ws.on("message", function incoming(message) {
    console.log("received: %s", message);
    // 回显消息
    ws.send(JSON.stringify({ status: "ok", echo: message }));
  });
  ws.send(JSON.stringify({ status: "connected" }));
});

console.log("WebSocket server running on ws://localhost:8787");
