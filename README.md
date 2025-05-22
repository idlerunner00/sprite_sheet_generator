# Animated 2D Spritesheet Generator & Viewer

This project consists of two main parts:
1.  A **Python-based generator** that uses Blender to render 3D models (FBX/OBJ) into animated 2D spritesheets.
2.  An **HTML/JavaScript viewer** to display and interact with these generated spritesheets.

## Features

**Generator (Python/Blender):**
* Processes 3D models from an input directory.
* Configurable rendering settings (resolution, angles, animation types) via `config.ini`.
* Supports FBX files for animations and material references, and OBJ files for material references.
* Automated rendering of animation frames from multiple angles.
* Assembles rendered frames into PNG spritesheets.
* Generates JSON metadata for each spritesheet (dimensions, frame counts, etc.).
* Creates a `manifest_spritesheets.json` file for easy integration with the viewer.

**Viewer (HTML/JS):**
* Loads and displays spritesheets based on the `manifest_spritesheets.json`.
* Interactive character control:
    * Movement (WASD/Arrow keys).
    * Orientation (Keyboard or Mouse over canvas).
* Supports multiple animation states per model (e.g., Idle, Walking, Fly, Dance) selectable via key presses (Shift for Fly, R for Dance).
* Adjustable animation speed and character movement speed via sliders.
* Toggleable dust particle effects during movement.
* Option to lock character movement while still allowing orientation changes.
* Model selection via dropdown or "Next Model" button.

## Directory Structure (Simplified)

/SpriteSheetGenerator
├── input_models/
│   └── YourModelName/
│       ├── Idle.fbx
│       ├── Walking.fbx
│       └── YourModelName_material.fbx (or .obj for material) 
├── output_spritesheets/  # Output of the Python generator
│   ├── YourModel_Animationtype_spritesheet_angle_rows.png
│   ├── YourModel_Animationtype_spritesheet_angle_rows.json
│   └── manifest_spritesheets.json
├── src/
│   ├── main_local2.py             # Main orchestration script
│   └── render_animated_spritesheet.py # Blender rendering script
├── viewer/                    # Files for the HTML viewer
│   ├── index.html
│   ├── style.css
│   ├── viewer.js
│   └── assets/
│       └── spritesheets/      # Spritesheets copied here for viewer
└── config.ini                 # Main configuration for the generator

## Prerequisites

* **Python 3.x**
* **Blender 4.1:** (Ensure the executable path is correctly set in `config.ini`)
* **Pillow (Python Imaging Library):** `pip install Pillow`
* A modern **Web Browser** (for the viewer)

## Setup & Configuration

1.  **Clone/Download:** Get all project files.
2.  **Install Dependencies:** Ensure Python, Blender, and Pillow are installed.
3.  **Input Models:**
    * Create the `input_models/` directory if it doesn't exist.
    * Inside `input_models/`, create a subdirectory for each 3D model you want to process (e.g., `MyCharacter`).
    * Place your animation FBX files (e.g., `Idle.fbx`, `Walking.fbx`, `Roll.fbx`, `Dance.fbx`) and any material reference FBX/OBJ files into the respective model's subdirectory. The script expects specific animation names as defined in `SUPPORTED_ANIMATIONS` in `main_local2.py`.
4.  **Configure `config.ini`:**
    * Open `config.ini` in a text editor.
    * **Crucial:** Set `blender_executable_path` under the `[Blender]` section to the correct path of your Blender executable.
    * Adjust settings under `[RenderSettings]`, `[Animation]`, `[Camera]`, and `[ModelProcessing]` as needed. You can create animation-specific sections (e.g., `[CameraIdle]`, `[RenderSettingsWalking]`) for finer control. If not found, it falls back to default animation type sections (e.g., `[CameraWalking]`) or generic sections (e.g., `[Camera]`), and finally to hardcoded defaults.
    * `desired_model_height` in `[ModelProcessing]` can be used to automatically scale models to a consistent height. Set to `0` to disable.

## Usage

### 1. Generating Spritesheets

1.  Open your terminal or command prompt.
2.  Navigate to the `src/` directory of the project.
3.  Run the main script: `python main_local2.py`
4.  The script will scan the `input_models/` directory and list available model-animation sets.
5.  Follow the on-screen prompts to select which model-animation sets you want to render.
6.  The generator will call Blender in the background to render frames and then assemble them into spritesheets.
7.  Generated spritesheets (PNGs), their JSON metadata, and the `manifest_spritesheets.json` will be saved in the `output_spritesheets/` directory.
8.  Temporary frames will be created in `temp_frames/` during processing and (usually) deleted afterwards.

### 2. Viewing Spritesheets

1.  **Copy Assets:**
    * Manually copy the entire contents of the `output_spritesheets/` directory (including `manifest_spritesheets.json` and all PNG/JSON pairs) into the `viewer/assets/spritesheets/` directory. The viewer is configured to look for assets in this specific sub-path.
2.  **Start Webserver**
    * Start Webserver inside the Sprite Viewer
    * python -m http.server
    * Connect via http://localhost:8000/
3.  **Interact:**
    * Use the dropdown menu or "Next Model" button to select different character models.
    * Use WASD or Arrow keys to move the character and change its orientation (if movement is not locked).
    * Move the mouse over the canvas to control character orientation.
    * Press `Shift` to toggle the "Roll" (flying) animation and increase movement speed.
    * Press `R` to toggle the "Dance" animation.
    * Use the sliders to adjust animation and movement speeds.
    * Use the buttons to toggle dust particles and movement lock.

## Notes

* The Python generator relies heavily on the structure and naming within `config.ini` and the expected animation file names (e.g., `Idle.fbx`).
* The viewer expects `manifest_spritesheets.json` and the corresponding spritesheet assets to be in `viewer/assets/spritesheets/`.
* Blender error messages and output will be printed to the console when `main_local2.py` is running.
* Mixamo will give you error messages if you upload .fbx files downloaded from TripoAI before. Use .obj. Import .fbx into Blender and Export as .obj.
