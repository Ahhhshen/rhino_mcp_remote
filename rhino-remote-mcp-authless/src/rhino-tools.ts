import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getFunctionCategory } from "./rhino-script-categories";
import { sendRhinoCommand } from "./index";
import type { Env } from "./index";

// Define the Rhino tools class
export class RhinoTools {
  constructor(private server: McpServer) {
    this.initializeTools();
  }

  private initializeTools() {
    // Get Rhino scene info
    this.server.tool(
      "get_rhino_scene_info",
      "Get basic information about the current Rhino scene",
      async (extra) => {
        const result = await sendRhinoCommand(
          extra.requestId as unknown as Env,
          "get_rhino_scene_info"
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }
    );

    // Get Rhino layers
    this.server.tool(
      "get_rhino_layers",
      "Get list of layers in Rhino",
      async (extra) => {
        const result = await sendRhinoCommand(
          extra.requestId as unknown as Env,
          "get_rhino_layers"
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }
    );

    // Get Rhino objects with metadata
    this.server.tool(
      "get_rhino_objects_with_metadata",
      {
        filters: z.record(z.any()).optional(),
        metadata_fields: z.array(z.string()).optional(),
      },
      async (args, extra) => {
        const result = await sendRhinoCommand(
          extra.requestId as unknown as Env,
          "get_rhino_objects_with_metadata",
          {
            filters: args.filters || {},
            metadata_fields: args.metadata_fields,
          }
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }
    );

    // Capture Rhino viewport
    this.server.tool(
      "capture_rhino_viewport",
      {
        layer: z.string().optional(),
        show_annotations: z.boolean().optional(),
        max_size: z.number().optional(),
      },
      async (args: any, extra: any) => {
        const result = await sendRhinoCommand(
          extra.requestId as unknown as Env,
          "capture_rhino_viewport",
          {
            layer: args.layer,
            show_annotations: args.show_annotations,
            max_size: args.max_size,
          }
        );

        if (result.type === "image") {
          return {
            content: [
              {
                type: "image",
                data: result.source.data,
                mimeType: "image/jpeg",
              },
            ],
          };
        }

        throw new Error(result.text || "Failed to capture viewport");
      }
    );

    // Execute Rhino code
    this.server.tool(
      "execute_rhino_code",
      {
        code: z.string(),
      },
      async (args: any, extra: any) => {
        const result = await sendRhinoCommand(
          extra.requestId as unknown as Env,
          "execute_code",
          { code: args.code }
        );

        if (result.status === "error") {
          const errorMsg = `Error: ${result.message}`;
          const printedOutput = result.printed_output || [];
          return {
            content: [
              {
                type: "text",
                text:
                  printedOutput.length > 0
                    ? `${errorMsg}\n\nPrinted output before error:\n${printedOutput.join(
                        "\n"
                      )}`
                    : errorMsg,
              },
            ],
          };
        }

        const response = result.result || "Code executed successfully";
        const printedOutput = result.printed_output || [];
        return {
          content: [
            {
              type: "text",
              text:
                printedOutput.length > 0
                  ? `${response}\n\nPrinted output:\n${printedOutput.join(
                      "\n"
                    )}`
                  : response,
            },
          ],
        };
      }
    );

    // Get selected Rhino objects
    this.server.tool(
      "get_rhino_selected_objects",
      {
        include_lights: z.boolean().optional(),
        include_grips: z.boolean().optional(),
      },
      async (args: any, extra: any) => {
        const result = await sendRhinoCommand(
          extra.requestId as unknown as Env,
          "get_rhino_selected_objects",
          {
            include_lights: args.include_lights,
            include_grips: args.include_grips,
          }
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        };
      }
    );

    // Look up RhinoScriptSyntax documentation
    this.server.tool(
      "look_up_RhinoScriptSyntax",
      {
        function_name: z.string(),
      },
      async (args: any, extra: any) => {
        // Get the category for the function
        const category = getFunctionCategory(args.function_name);
        if (!category) {
          return {
            content: [
              {
                type: "text",
                text: `Function '${args.function_name}' not found in RhinoScriptSyntax categories`,
              },
            ],
          };
        }

        const result = await sendRhinoCommand(
          extra.requestId as unknown as Env,
          "look_up_RhinoScriptSyntax",
          {
            function_name: args.function_name,
            category,
          }
        );
        return {
          content: [{ type: "text", text: JSON.stringify(result) }],
        };
      }
    );
  }
}
