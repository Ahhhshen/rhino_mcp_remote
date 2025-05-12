# RhinoMCP Remote - Cloud-Hosted Rhino Model Context Protocol

This is a proprietary cloud-hosted implementation of the RhinoMCP protocol. This project extends Reer's [open-source RhinoMCP project](https://github.com/JunlingZhuang/rhino_mcp) with remote hosting capabilities via Cloudflare, allowing for seamless integration between Rhino/Grasshopper and LLMs through the Model Context Protocol (MCP).

**IMPORTANT: This is proprietary software owned by Reer, Inc. All rights reserved.**

## Key Differences from the Open Source Version

- **Cloud-Hosted Architecture**: Deployed on Cloudflare for reliable, scalable remote access
- **Enhanced Security**: Additional authentication and access control features
- **Proprietary Extensions**: Custom features exclusive to this implementation


## Features

#### Rhino

- **Two-way communication**: Connect Claude AI to Rhino through a socket-based server
- **Object manipulation and management**: Create and modify 3D objects in Rhino including metadata
- **Layer management**: View and interact with Rhino layers
- **Scene inspection**: Get detailed information about the current Rhino scene (incl. screencapture)
- **Code execution**: Run arbitrary Python code in Rhino from Claude
- **Object selection**: Get information about the currently selected objects in Rhino
- **RhinoScriptSyntax documentation**: Look up the documentation for a RhinoScriptSyntax 
- ...

## Contributing

We welcome contributions to the RhinoMCP project! If you're interested in helping, here are some ways to contribute:

1. **Bug Reports**: If you find a bug, please create an issue with a detailed description of the problem and steps to reproduce it.
2. **Feature Requests**: Have an idea for a new feature? Open an issue to discuss it.
3. **Code Contributions**: Want to add a feature or fix a bug?
   - Fork the repository
   - Create a new branch for your changes
   - Submit a pull request with a clear description of your changes

Please ensure your code follows the existing style and includes appropriate documentation.

## Cloudflare Deployment

This implementation is designed to be deployed on Cloudflare Workers or Pages. Deployment instructions:

1. Configure your Cloudflare account and API tokens
2. Set up the deployment pipeline using the provided scripts
3. Deploy the server endpoints for remote access

Detailed deployment instructions can be found in the `docs/cloudflare-deployment.md` file.

## License

This is proprietary software owned by Reer, Inc. All rights reserved. 

The original open-source RhinoMCP project is licensed under MIT and can be found at [original repo link].

## Disclaimer

This software is provided "as is", without warranty of any kind. Reer, Inc. makes no warranties with respect to the software, including but not limited to quality, reliability, compatibility, or fitness for a particular purpose.

By using this software, you acknowledge and agree that Reer, Inc. shall not be liable for any direct, indirect, incidental, special, or consequential damages arising out of the use or inability to use the software.

This is a proprietary product in active development. Unauthorized use is strictly prohibited.

