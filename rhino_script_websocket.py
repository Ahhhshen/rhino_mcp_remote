"""
Rhino MCP - Rhino-side Script (WebSocket Client Version)
Connects to external MCP server and executes Rhino commands.
"""

import json
import System
import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs
import os
import platform
import traceback
import sys
import base64
import time
from System.Drawing import Bitmap
from System.Drawing.Imaging import ImageFormat
from System.IO import MemoryStream
from datetime import datetime
import websocket
import threading

# Configuration
SERVER_HOST = 'rhino-remote-mcp-authless.shawchen.workers.dev'
USE_SSL = True  # Must be True for Cloudflare Worker
RETRY_INTERVAL = 5  # Seconds between retries

# Add constant for annotation layer
ANNOTATION_LAYER = "MCP_Annotations"

VALID_METADATA_FIELDS = {
    'required': ['id', 'name', 'type', 'layer'],
    'optional': [
        'short_id',      # Short identifier (DDHHMMSS format)
        'created_at',    # Timestamp of creation
        'bbox',          # Bounding box coordinates
        'description',   # Object description
        'user_text'      # All user text key-value pairs
    ]
}

def get_log_dir():
    """Get the appropriate log directory based on the platform"""
    home_dir = os.path.expanduser("~")
    
    # Platform-specific log directory
    if platform.system() == "Darwin":  # macOS
        log_dir = os.path.join(home_dir, "Library", "Application Support", "RhinoMCP", "logs")
    elif platform.system() == "Windows":
        log_dir = os.path.join(home_dir, "AppData", "Local", "RhinoMCP", "logs")
    else:  # Linux and others
        log_dir = os.path.join(home_dir, ".rhino_mcp", "logs")
    
    return log_dir

def log_message(message):
    """Log a message to both Rhino's command line and log file"""
    # Print to Rhino's command line
    Rhino.RhinoApp.WriteLine(message)
    
    # Log to file
    try:
        log_dir = get_log_dir()
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, "rhino_mcp.log")
        
        # Log platform info on first run
        if not os.path.exists(log_file):
            with open(log_file, "w") as f:
                f.write("=== RhinoMCP Log ===\n")
                f.write("Platform: {0}\n".format(platform.system()))
                f.write("Python Version: {0}\n".format(sys.version))
                f.write("Rhino Version: {0}\n".format(Rhino.RhinoApp.Version))
                f.write("==================\n\n")
        
        with open(log_file, "a") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write("[{0}] {1}\n".format(timestamp, message))
    except Exception as e:
        Rhino.RhinoApp.WriteLine("Failed to write to log file: {0}".format(str(e)))

class RhinoMCPClient:
    def __init__(self, host=SERVER_HOST):
        self.host = host
        self.ws = None
        self.running = False
        self.thread = None
        self.retry_count = 0
        self.last_error = None

    def on_message(self, ws, message):
        """Handle incoming messages from the server"""
        try:
            command = json.loads(message)
            log_message(f"Received command: {command}")
            
            # Execute the command and get response
            response = self.execute_command(command)
            
            # Add the request ID to the response
            if 'id' in command:
                response['id'] = command['id']
            
            # Send response back to server
            ws.send(json.dumps(response))
            log_message("Response sent successfully")
            
        except json.JSONDecodeError as e:
            log_message(f"Invalid JSON received: {str(e)}")
            error_response = {"status": "error", "message": "Invalid JSON format"}
            ws.send(json.dumps(error_response))
        except Exception as e:
            log_message(f"Error handling message: {str(e)}")
            traceback.print_exc()
            error_response = {"status": "error", "message": str(e)}
            ws.send(json.dumps(error_response))

    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        self.last_error = str(error)
        log_message(f"WebSocket error: {str(error)}")
        if hasattr(ws, 'headers'):
            log_message(f"WebSocket headers: {ws.headers}")
        if hasattr(ws, 'status'):
            log_message(f"WebSocket status: {ws.status}")

    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        log_message(f"WebSocket connection closed. Code: {close_status_code}, Message: {close_msg}")
        self.running = False
        # Try to reconnect
        if self.retry_count < 100:  # Limit retries to prevent infinite loop
            self.retry_count += 1
            log_message(f"Retrying connection in {RETRY_INTERVAL} seconds... (Attempt {self.retry_count})")
            time.sleep(RETRY_INTERVAL)
            self.connect()

    def on_open(self, ws):
        """Handle WebSocket connection open"""
        log_message("WebSocket connection established")
        if hasattr(ws, 'headers'):
            log_message(f"WebSocket headers: {ws.headers}")
        self.running = True
        self.retry_count = 0  # Reset retry count on successful connection

    def connect(self):
        """Connect to the WebSocket server"""
        try:
            protocol = "wss" if USE_SSL else "ws"
            uri = f"{protocol}://{self.host}"
            log_message(f"Connecting to {uri}...")

            headers = [
                f"Origin: https://{self.host}"
            ]

            self.ws = websocket.WebSocketApp(
                uri,
                header=headers,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )

            self.thread = threading.Thread(target=self.ws.run_forever)
            self.thread.daemon = True
            self.thread.start()

            timeout = 10  # 10 seconds timeout
            start_time = time.time()
            while not self.running and time.time() - start_time < timeout:
                time.sleep(0.1)
                if self.last_error:
                    log_message(f"Connection error while waiting: {self.last_error}")

            if not self.running:
                raise Exception("Failed to establish WebSocket connection within timeout")

            return True
        except Exception as e:
            log_message(f"Failed to connect: {str(e)}")
            if self.last_error:
                log_message(f"Last error: {self.last_error}")
            return False

    def stop(self):
        """Stop the WebSocket client"""
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=1)
        self.running = False

    def execute_command(self, command):
        """Execute a command received from the server"""
        try:
            command_type = command.get("type")
            params = command.get("params", {})
            
            if command_type == "get_rhino_scene_info":
                return self._get_rhino_scene_info(params)
            elif command_type == "_rhino_create_cube":
                return self._create_cube(params)
            elif command_type == "get_rhino_layers":
                return self._get_rhino_layers()
            elif command_type == "execute_code":
                return self._execute_rhino_code(params)
            elif command_type == "get_rhino_objects_with_metadata":
                return self._get_rhino_objects_with_metadata(params)
            elif command_type == "capture_rhino_viewport":
                return self._capture_rhino_viewport(params)
            elif command_type == "add_rhino_object_metadata":
                return self._add_rhino_object_metadata(
                    params.get("object_id"), 
                    params.get("name"), 
                    params.get("description")
                )
            elif command_type == "get_rhino_selected_objects":
                return self._get_rhino_selected_objects(params)
            else:
                return {"status": "error", "message": "Unknown command type"}
                
        except Exception as e:
            log_message(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _get_rhino_scene_info(self, params=None):
        """Get simplified scene information focusing on layers and example objects"""
        try:
            doc = sc.doc
            if not doc:
                return {
                    "status": "error",
                    "message": "No active document"
                }
            
            log_message("Getting simplified scene info...")
            layers_info = []
            
            for layer in doc.Layers:
                layer_objects = [obj for obj in doc.Objects if obj.Attributes.LayerIndex == layer.Index]
                example_objects = []
                
                for obj in layer_objects[:5]:  # Limit to 5 example objects per layer
                    try:
                        # Convert NameValueCollection to dictionary
                        user_strings = {}
                        if obj.Attributes.GetUserStrings():
                            for key in obj.Attributes.GetUserStrings():
                                user_strings[key] = obj.Attributes.GetUserString(key)
                        
                        obj_info = {
                            "id": str(obj.Id),
                            "name": obj.Name or "Unnamed",
                            "type": obj.Geometry.GetType().Name if obj.Geometry else "Unknown",
                            "metadata": user_strings  # Now using the converted dictionary
                        }
                        example_objects.append(obj_info)
                    except Exception as e:
                        log_message("Error processing object: {0}".format(str(e)))
                        continue
                
                layer_info = {
                    "full_path": layer.FullPath,
                    "object_count": len(layer_objects),
                    "is_visible": layer.IsVisible,
                    "is_locked": layer.IsLocked,
                    "example_objects": example_objects
                }
                layers_info.append(layer_info)
            
            response = {
                "status": "success",
                "layers": layers_info
            }
            
            log_message("Simplified scene info collected successfully")
            return response
            
        except Exception as e:
            log_message("Error getting simplified scene info: {0}".format(str(e)))
            return {
                "status": "error",
                "message": str(e),
                "layers": []
            }
    
    def _create_cube(self, params):
        """Create a cube in the scene"""
        try:
            size = float(params.get("size", 1.0))
            location = params.get("location", [0, 0, 0])
            name = params.get("name", "Cube")
            
            # Create cube using RhinoCommon
            box = Rhino.Geometry.Box(
                Rhino.Geometry.Plane.WorldXY,
                Rhino.Geometry.Interval(0, size),
                Rhino.Geometry.Interval(0, size),
                Rhino.Geometry.Interval(0, size)
            )
            
            # Move to specified location
            transform = Rhino.Geometry.Transform.Translation(
                location[0] - box.Center.X,
                location[1] - box.Center.Y,
                location[2] - box.Center.Z
            )
            box.Transform(transform)
            
            # Add to document
            id = sc.doc.Objects.AddBox(box)
            if id != System.Guid.Empty:
                obj = sc.doc.Objects.Find(id)
                if obj:
                    obj.Name = name
                    sc.doc.Views.Redraw()
                    return {
                        "status": "success",
                        "message": "Created cube with size {0}".format(size),
                        "id": str(id)
                    }
            
            return {"status": "error", "message": "Failed to create cube"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _get_rhino_layers(self):
        """Get information about all layers"""
        try:
            doc = sc.doc
            layers = []
            
            for layer in doc.Layers:
                layers.append({
                    "id": layer.Index,
                    "name": layer.Name,
                    "object_count": layer.ObjectCount,
                    "is_visible": layer.IsVisible,
                    "is_locked": layer.IsLocked
                })
            
            return {
                "status": "success",
                "layers": layers
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _execute_rhino_code(self, params):
        """Execute arbitrary Python code"""
        try:
            code = params.get("code", "")
            if not code:
                return {"status": "error", "message": "No code provided"}
            
            log_message("Executing code: {0}".format(code))
            
            # Create a new scope for code execution
            local_dict = {}
            
            # Create a list to store printed output
            printed_output = []
            
            # Override print function to capture output
            def custom_print(*args, **kwargs):
                output = " ".join(str(arg) for arg in args)
                printed_output.append(output)
                # Also print to Rhino's command line
                Rhino.RhinoApp.WriteLine(output)
            
            # Add custom print to local scope
            local_dict['print'] = custom_print
            
            try:
                # Execute the code
                exec(code, globals(), local_dict)
                
                # Get result from local_dict or use a default message
                result = local_dict.get("result", "Code executed successfully")
                log_message("Code execution completed. Result: {0}".format(result))
                
                response = {
                    "status": "success",
                    "result": str(result),
                    "printed_output": printed_output,  # Include captured print output
                    #"variables": {k: str(v)  k, v in local_dict.items() if not k.startswith('__')}
                }
                
                log_message("Sending response: {0}".format(json.dumps(response)))
                return response
                
            except Exception as e:
                # hint = "Did you use f-string formatting? You have to use IronPython here that doesn't support this."
                error_response = {
                    "status": "error",
                    "message": str(e),
                    "printed_output": printed_output  # Include any output captured before the error
                }
                log_message("Error: {0}".format(error_response))
                return error_response
                
        except Exception as e:
            # hint = "Did you use f-string formatting? You have to use IronPython here that doesn't support this."
            error_response = {
                "status": "error",
                "message": str(e),
            }
            log_message("System error: {0}".format(error_response))
            return error_response

    def _add_rhino_object_metadata(self, obj_id, name=None, description=None):
        """Add standardized metadata to an object"""
        try:
            import json
            import time
            from datetime import datetime
            
            # Generate short ID
            short_id = datetime.now().strftime("%d%H%M%S")
            
            # Get bounding box
            bbox = rs.BoundingBox(obj_id)
            bbox_data = [[p.X, p.Y, p.Z] for p in bbox] if bbox else []
            
            # Get object type
            obj = sc.doc.Objects.Find(obj_id)
            obj_type = obj.Geometry.GetType().Name if obj else "Unknown"
            
            # Standard metadata
            metadata = {
                "short_id": short_id,
                "created_at": time.time(),
                "layer": rs.ObjectLayer(obj_id),
                "type": obj_type,
                "bbox": bbox_data
            }
            
            # User-provided metadata
            if name:
                rs.ObjectName(obj_id, name)
                metadata["name"] = name
            else:
                # Auto-generate name if none provided
                auto_name = "{0}_{1}".format(obj_type, short_id)
                rs.ObjectName(obj_id, auto_name)
                metadata["name"] = auto_name
                
            if description:
                metadata["description"] = description
                
            # Store metadata as user text (convert bbox to string for storage)
            user_text_data = metadata.copy()
            user_text_data["bbox"] = json.dumps(bbox_data)
            
            # Add all metadata as user text
            for key, value in user_text_data.items():
                rs.SetUserText(obj_id, key, str(value))
                
            return {"status": "success"}
        except Exception as e:
            log_message("Error adding metadata: " + str(e))
            return {"status": "error", "message": str(e)}

    def _get_rhino_objects_with_metadata(self, params):
        """Get objects with their metadata, with optional filtering"""
        try:
            import re
            import json
            
            filters = params.get("filters", {})
            metadata_fields = params.get("metadata_fields")
            layer_filter = filters.get("layer")
            name_filter = filters.get("name")
            id_filter = filters.get("short_id")
            
            # Validate metadata fields
            all_fields = VALID_METADATA_FIELDS['required'] + VALID_METADATA_FIELDS['optional']
            if metadata_fields:
                invalid_fields = [f for f in metadata_fields if f not in all_fields]
                if invalid_fields:
                    return {
                        "status": "error",
                        "message": "Invalid metadata fields: " + ", ".join(invalid_fields),
                        "available_fields": all_fields
                    }
            
            objects = []
            
            for obj in sc.doc.Objects:
                obj_id = obj.Id
                
                # Apply filters
                if layer_filter:
                    layer = rs.ObjectLayer(obj_id)
                    pattern = "^" + layer_filter.replace("*", ".*") + "$"
                    if not re.match(pattern, layer, re.IGNORECASE):
                        continue
                    
                if name_filter:
                    name = obj.Name or ""
                    pattern = "^" + name_filter.replace("*", ".*") + "$"
                    if not re.match(pattern, name, re.IGNORECASE):
                        continue
                    
                if id_filter:
                    short_id = rs.GetUserText(obj_id, "short_id") or ""
                    if short_id != id_filter:
                        continue
                    
                # Build base object data with required fields
                obj_data = {
                    "id": str(obj_id),
                    "name": obj.Name or "Unnamed",
                    "type": obj.Geometry.GetType().Name,
                    "layer": rs.ObjectLayer(obj_id)
                }
                
                # Get user text data and parse stored values
                stored_data = {}
                for key in rs.GetUserText(obj_id):
                    value = rs.GetUserText(obj_id, key)
                    if key == "bbox":
                        try:
                            value = json.loads(value)
                        except:
                            value = []
                    elif key == "created_at":
                        try:
                            value = float(value)
                        except:
                            value = 0
                    stored_data[key] = value
                
                # Build metadata based on requested fields
                if metadata_fields:
                    metadata = {k: stored_data[k] for k in metadata_fields if k in stored_data}
                else:
                    metadata = {k: v for k, v in stored_data.items() 
                              if k not in VALID_METADATA_FIELDS['required']}
                
                # Only include user_text if specifically requested
                if not metadata_fields or 'user_text' in metadata_fields:
                    user_text = {k: v for k, v in stored_data.items() 
                               if k not in metadata}
                    if user_text:
                        obj_data["user_text"] = user_text
                
                # Add metadata if we have any
                if metadata:
                    obj_data["metadata"] = metadata
                    
                objects.append(obj_data)
            
            return {
                "status": "success",
                "count": len(objects),
                "objects": objects,
                "available_fields": all_fields
            }
            
        except Exception as e:
            log_message("Error filtering objects: " + str(e))
            return {
                "status": "error",
                "message": str(e),
                "available_fields": all_fields
            }

    def _capture_rhino_viewport(self, params):
        """Capture viewport with optional annotations and layer filtering"""
        try:
            layer_name = params.get("layer")
            show_annotations = params.get("show_annotations", True)
            max_size = params.get("max_size", 800)  # Default max dimension
            original_layer = rs.CurrentLayer()
            temp_dots = []

            if show_annotations:
                # Ensure annotation layer exists and is current
                if not rs.IsLayer(ANNOTATION_LAYER):
                    rs.AddLayer(ANNOTATION_LAYER, color=(255, 0, 0))
                rs.CurrentLayer(ANNOTATION_LAYER)
                
                # Create temporary text dots for each object
                for obj in sc.doc.Objects:
                    if layer_name and rs.ObjectLayer(obj.Id) != layer_name:
                        continue
                        
                    bbox = rs.BoundingBox(obj.Id)
                    if bbox:
                        pt = bbox[1]  # Use top corner of bounding box
                        short_id = rs.GetUserText(obj.Id, "short_id")
                        if not short_id:
                            short_id = datetime.now().strftime("%d%H%M%S")
                            rs.SetUserText(obj.Id, "short_id", short_id)
                        
                        name = rs.ObjectName(obj.Id) or "Unnamed"
                        text = "{0}\n{1}".format(name, short_id)
                        
                        dot_id = rs.AddTextDot(text, pt)
                        rs.TextDotHeight(dot_id, 8)
                        temp_dots.append(dot_id)
            
            try:
                view = sc.doc.Views.ActiveView
                memory_stream = MemoryStream()
                
                # Capture to bitmap
                bitmap = view.CaptureToBitmap()
                
                # Calculate new dimensions while maintaining aspect ratio
                width, height = bitmap.Width, bitmap.Height
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                
                # Create resized bitmap
                resized_bitmap = Bitmap(bitmap, new_width, new_height)
                
                # Save as JPEG (IronPython doesn't support quality parameter)
                resized_bitmap.Save(memory_stream, ImageFormat.Jpeg)
                
                bytes_array = memory_stream.ToArray()
                image_data = base64.b64encode(bytes(bytearray(bytes_array))).decode('utf-8')
                
                # Clean up
                bitmap.Dispose()
                resized_bitmap.Dispose()
                memory_stream.Dispose()
                
            finally:
                if temp_dots:
                    rs.DeleteObjects(temp_dots)
                rs.CurrentLayer(original_layer)
            
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_data
                }
            }
            
        except Exception as e:
            log_message("Error capturing viewport: " + str(e))
            if 'original_layer' in locals():
                rs.CurrentLayer(original_layer)
            return {
                "type": "text",
                "text": "Error capturing viewport: " + str(e)
            }

    def _get_rhino_selected_objects(self, params):
        """Get objects that are currently selected in Rhino"""
        try:            
            include_lights = params.get("include_lights", False)
            include_grips = params.get("include_grips", False)
            
            # Get selected objects using rhinoscriptsyntax
            selected_ids = rs.SelectedObjects(include_lights, include_grips)
            
            if not selected_ids:
                return {
                    "status": "success",
                    "message": "No objects selected",
                    "count": 0,
                    "objects": []
                }
                
            # Collect object data
            selected_objects = []
            for obj_id in selected_ids:
                # Get basic object information
                obj = sc.doc.Objects.Find(obj_id)
                if not obj:
                    continue
                    
                obj_data = {
                    "id": str(obj_id),
                    "name": obj.Name or "Unnamed",
                    "type": obj.Geometry.GetType().Name if obj.Geometry else "Unknown",
                    "layer": rs.ObjectLayer(obj_id)
                }
                
                # Get metadata from user strings
                user_strings = {}
                for key in rs.GetUserText(obj_id):
                    user_strings[key] = rs.GetUserText(obj_id, key)
                
                if user_strings:
                    obj_data["metadata"] = user_strings
                    
                selected_objects.append(obj_data)
                
            return {
                "status": "success",
                "count": len(selected_objects),
                "objects": selected_objects
            }
            
        except Exception as e:
            log_message("Error getting selected objects: " + str(e))
            return {"status": "error", "message": str(e)}

# Create and start client
client = RhinoMCPClient()

try:
    if client.connect():
        log_message(f"RhinoMCP WebSocket client script loaded. Connected to ws://{SERVER_HOST}")
        log_message("To stop the client, close Rhino or interrupt the script.")
    else:
        log_message("Failed to connect to WebSocket server")
except Exception as e:
    log_message(f"Failed to start WebSocket client: {str(e)}") 