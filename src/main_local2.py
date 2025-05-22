import os
import sys
import subprocess
import configparser
import shutil
import glob
from PIL import Image
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

INPUT_DIR_ROOT = os.path.join(BASE_DIR, 'input_models')
OUTPUT_DIR_SPRITESHEETS = os.path.join(BASE_DIR, 'output_spritesheets')
TEMP_DIR_FRAMES_ROOT = os.path.join(BASE_DIR, 'temp_frames')
BLENDER_ANIM_SCRIPT_PATH = os.path.join(SCRIPT_DIR, 'render_animated_spritesheet.py')
MAIN_CONFIG_FILE_PATH = os.path.join(BASE_DIR, 'config.ini')

SUPPORTED_ANIMATIONS = {
    "Idle": "Idle.fbx",
    "Fly": "Fly.fbx",
    "Walking": "Walking.fbx",
    "Dance": "Dance.fbx"
}
DEFAULT_ANIMATION_TYPE_FALLBACK = "Walking"

def setup_directories():
    for dir_path in [INPUT_DIR_ROOT, OUTPUT_DIR_SPRITESHEETS, TEMP_DIR_FRAMES_ROOT]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Directory created: {dir_path}")

def load_main_config():
    if not os.path.exists(MAIN_CONFIG_FILE_PATH):
        print(f"Error: Main configuration file not found: {MAIN_CONFIG_FILE_PATH}"); sys.exit(1)
    config = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
    config.read(MAIN_CONFIG_FILE_PATH)
    blender_path = config['Blender'].get('blender_executable_path', '')
    if not blender_path or not os.path.exists(blender_path):
        print(f"Error: Path to Blender application not found/invalid in config.ini: '{blender_path}'"); sys.exit(1)
    if not os.path.exists(BLENDER_ANIM_SCRIPT_PATH):
        print(f"Error: Blender animation script not found: {BLENDER_ANIM_SCRIPT_PATH}"); sys.exit(1)
    return config

def find_model_sets(input_root_dir):
    model_animation_sets = []
    print(f"\nSearching for model sets and animations in subdirectories of: {input_root_dir}")
    if not os.path.exists(input_root_dir) or not os.path.isdir(input_root_dir):
        print(f"Error: Input directory '{input_root_dir}' not found or not a directory.")
        sys.exit(1)

    for subdir_name in os.listdir(input_root_dir):
        subdir_path = os.path.join(input_root_dir, subdir_name)
        if os.path.isdir(subdir_path):
            print(f"  Checking subdirectory (model): {subdir_name}")
            all_fbx_files_in_subdir = sorted(glob.glob(os.path.join(subdir_path, "*.fbx")))
            obj_files_in_subdir = sorted(glob.glob(os.path.join(subdir_path, "*.obj")))

            if not all_fbx_files_in_subdir:
                print(f"    No FBX files found in {subdir_name}."); continue

            mat_ref_fbx_path, mat_ref_obj_path = None, None

            possible_mat_fbx = []
            for fbx_f in all_fbx_files_in_subdir:
                base, _ = os.path.splitext(os.path.basename(fbx_f))
                if base.lower().endswith(("_material", "_materials", "_mat", "_tex", "_texture", "_textures")):
                    possible_mat_fbx.append(fbx_f)
            if possible_mat_fbx:
                mat_ref_fbx_path = possible_mat_fbx[0]
                print(f"    Material FBX found: {os.path.basename(mat_ref_fbx_path)}")

            if not mat_ref_fbx_path:
                possible_mat_obj = []
                for obj_f in obj_files_in_subdir:
                    base_obj, _ = os.path.splitext(os.path.basename(obj_f))
                    if base_obj.lower().endswith(("_material", "_materials", "_mat", "_tex", "_texture", "_textures", "_ref", "_reference")):
                        possible_mat_obj.append(obj_f)
                if possible_mat_obj:
                    mat_ref_obj_path = possible_mat_obj[0]
                    print(f"    Material OBJ found: {os.path.basename(mat_ref_obj_path)}")
                elif obj_files_in_subdir:
                    pass

            animations_found_for_model = []
            for anim_type, anim_filename_pattern in SUPPORTED_ANIMATIONS.items():
                potential_anim_fbx_paths = [f for f in all_fbx_files_in_subdir if os.path.basename(f).lower() == anim_filename_pattern.lower()]

                if not potential_anim_fbx_paths and "_" in anim_filename_pattern:
                    suffix_to_find = "_" + anim_filename_pattern.split('_')[-1] if len(anim_filename_pattern.split('_')) > 1 else anim_filename_pattern
                    potential_anim_fbx_paths = [f for f in all_fbx_files_in_subdir if os.path.basename(f).lower().endswith(suffix_to_find.lower())]

                if potential_anim_fbx_paths:
                    anim_fbx_path = potential_anim_fbx_paths[0]
                    if mat_ref_fbx_path and os.path.abspath(anim_fbx_path) == os.path.abspath(mat_ref_fbx_path):
                        if len(potential_anim_fbx_paths) > 1:
                            anim_fbx_path = potential_anim_fbx_paths[1]
                            print(f"    Animation FBX for '{anim_type}' (alternative candidate): {os.path.basename(anim_fbx_path)}")
                        else:
                            print(f"    WARNING: Animation FBX '{os.path.basename(anim_fbx_path)}' for '{anim_type}' is the same as the material FBX. Using it for animation anyway.")
                    else:
                        print(f"    Animation FBX for '{anim_type}' found: {os.path.basename(anim_fbx_path)}")

                    model_animation_sets.append({
                        "model_name": subdir_name,
                        "animation_type": anim_type,
                        "anim_fbx_path": os.path.abspath(anim_fbx_path),
                        "material_ref_fbx_path": os.path.abspath(mat_ref_fbx_path) if mat_ref_fbx_path else None,
                        "material_ref_obj_path": os.path.abspath(mat_ref_obj_path) if mat_ref_obj_path else None,
                        "output_subdir_frames": os.path.abspath(os.path.join(TEMP_DIR_FRAMES_ROOT, f"{subdir_name}_{anim_type}")),
                        "output_spritesheet_dir": os.path.abspath(OUTPUT_DIR_SPRITESHEETS),
                        "spritesheet_base_name": f"{subdir_name}_{anim_type}"
                    })
                    animations_found_for_model.append(anim_type)

            if not animations_found_for_model:
                non_material_fbx = [f for f in all_fbx_files_in_subdir if (not mat_ref_fbx_path or os.path.abspath(f) != os.path.abspath(mat_ref_fbx_path))]
                if non_material_fbx:
                    generic_anim_fbx = non_material_fbx[0]
                    anim_type = DEFAULT_ANIMATION_TYPE_FALLBACK
                    print(f"    No specific animation FBXs found. Using generic FBX '{os.path.basename(generic_anim_fbx)}' as '{anim_type}'.")
                    model_animation_sets.append({
                        "model_name": subdir_name,
                        "animation_type": anim_type,
                        "anim_fbx_path": os.path.abspath(generic_anim_fbx),
                        "material_ref_fbx_path": os.path.abspath(mat_ref_fbx_path) if mat_ref_fbx_path else None,
                        "material_ref_obj_path": os.path.abspath(mat_ref_obj_path) if mat_ref_obj_path else None,
                        "output_subdir_frames": os.path.abspath(os.path.join(TEMP_DIR_FRAMES_ROOT, f"{subdir_name}_{anim_type}")),
                        "output_spritesheet_dir": os.path.abspath(OUTPUT_DIR_SPRITESHEETS),
                        "spritesheet_base_name": f"{subdir_name}_{anim_type}"
                    })
                else:
                    print(f"    WARNING: No suitable animation FBX files found in {subdir_name} (neither specific nor generic).")

    if not model_animation_sets:
        print("No model-animation sets found. Please ensure that input_models contains subdirectories with FBX files."); sys.exit(1)

    print("\nAvailable model-animation sets:")
    for i, anim_set in enumerate(model_animation_sets):
        mat_ref_display = "No explicit material reference"
        if anim_set['material_ref_fbx_path']:
            mat_ref_display = f"Mat-FBX: {os.path.basename(anim_set['material_ref_fbx_path'])}"
        elif anim_set['material_ref_obj_path']:
            mat_ref_display = f"Mat-OBJ: {os.path.basename(anim_set['material_ref_obj_path'])}"
        print(f"  {i+1}. Model: {anim_set['model_name']}, Animation: {anim_set['animation_type']} "
              f"(Anim-FBX: {os.path.basename(anim_set['anim_fbx_path'])}, {mat_ref_display})")

    while True:
        try:
            choices_str = input("Select model-animation sets by number (comma-separated, or 'all'): ")
            if not choices_str: raise ValueError("Input cannot be empty.")
            if choices_str.strip().lower() == 'all': return model_animation_sets

            selected_indices = []
            parts = choices_str.split(',')
            if not parts: raise ValueError("No numbers entered.")

            for c_part in parts:
                c_strip = c_part.strip()
                if not c_strip: continue
                num = int(c_strip) - 1
                if not (0 <= num < len(model_animation_sets)):
                    raise ValueError(f"Number {num+1} is outside the valid range 1-{len(model_animation_sets)}.")
                selected_indices.append(num)

            if not selected_indices: raise ValueError("No valid numbers selected.")
            unique_selected_indices = []
            for idx in selected_indices:
                if idx not in unique_selected_indices:
                    unique_selected_indices.append(idx)

            selected_sets = [model_animation_sets[idx] for idx in unique_selected_indices]
            return selected_sets
        except ValueError as e:
            print(f"Invalid input: {e}. Please enter numbers (e.g., 1 or 1,3), or 'all'.")

def generate_blender_config_ini(anim_set_info, main_config, temp_config_path):
    blender_cfg = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))

    blender_cfg['Paths'] = {
        'model_fbx': anim_set_info['anim_fbx_path'],
        'material_ref_fbx': anim_set_info['material_ref_fbx_path'] if anim_set_info['material_ref_fbx_path'] else "",
        'material_ref_obj': anim_set_info['material_ref_obj_path'] if anim_set_info['material_ref_obj_path'] else "",
        'output_dir': anim_set_info['output_subdir_frames']
    }

    current_animation_type_suffix = anim_set_info['animation_type']

    base_sections_to_process = ['RenderSettings', 'Animation', 'Camera', 'ModelProcessing']

    for section_base in base_sections_to_process:
        chosen_section_name_in_main_config = None

        specific_anim_type_section = f"{section_base}{current_animation_type_suffix}"
        if specific_anim_type_section in main_config:
            chosen_section_name_in_main_config = specific_anim_type_section
        elif current_animation_type_suffix.lower() != DEFAULT_ANIMATION_TYPE_FALLBACK.lower():
            default_anim_type_section = f"{section_base}{DEFAULT_ANIMATION_TYPE_FALLBACK}"
            if default_anim_type_section in main_config:
                chosen_section_name_in_main_config = default_anim_type_section

        if not chosen_section_name_in_main_config and section_base in main_config:
            chosen_section_name_in_main_config = section_base

        if chosen_section_name_in_main_config:
            blender_cfg[section_base] = main_config[chosen_section_name_in_main_config]
            print(f"Info: For Blender config section '{section_base}' for '{anim_set_info['model_name']}_{anim_set_info['animation_type']}' "
                  f"using '[{chosen_section_name_in_main_config}]' from main config.ini.")
        else:
            print(f"Warning: No configuration section for '{section_base}' for '{current_animation_type_suffix}' found (searched variants: "
                  f"'{specific_anim_type_section}', "
                  f"'{f'{section_base}{DEFAULT_ANIMATION_TYPE_FALLBACK}' if current_animation_type_suffix.lower() != DEFAULT_ANIMATION_TYPE_FALLBACK.lower() else 'N/A'}', "
                  f"'{section_base}') in config.ini.")
            if section_base == 'RenderSettings':
                print(f"  -> Using hardcoded default values for section '{section_base}'.")
                blender_cfg[section_base] = {
                    'resolution_x': '128', 'resolution_y': '128', 'rotation_steps': '8',
                    'rotation_axis': 'Z', 'eevee_taa_render_samples': '16',
                    'film_transparent': 'True', 'debug_no_transparent_background': 'False',
                    'verbose_render_loop': 'False'
                }
            elif section_base == 'Animation':
                print(f"  -> Creating empty section '{section_base}' (defaults will be handled in Blender script).")
                blender_cfg[section_base] = {'anim_start_frame': '', 'anim_end_frame': ''}
            elif section_base == 'Camera':
                print(f"  -> Using hardcoded default values for section '{section_base}'.")
                blender_cfg[section_base] = {
                    'camera_distance': '7.0', 'camera_elevation_degrees': '20.0',
                    'camera_target_z_offset': '1.0', 'ortho_scale_padding_factor': '1.15',
                    'ortho_scale_fallback': '4.0', 'key_light_energy': '3.0',
                    'key_light_angle_softness': '10.0', 'fill_light_energy': '1.5',
                    'fill_light_angle_softness': '15.0',
                    'ambient_light_color': '0.1,0.1,0.1,1.0',
                    'ambient_light_strength': '0.5'
                }
            elif section_base == 'ModelProcessing':
                print(f"  -> Creating section '{section_base}' with default value (scaling disabled).")
                blender_cfg[section_base] = {'desired_model_height': '0'}
            else:
                print(f"  -> Creating empty section '{section_base}'.")
                blender_cfg[section_base] = {}

    default_structure = {
        'RenderSettings': {'resolution_x':'128','resolution_y':'128', 'rotation_steps':'8', 'film_transparent': 'True'},
        'Animation': {'anim_start_frame': '', 'anim_end_frame': ''},
        'Camera': {'ortho_scale_fallback':'5.0', 'camera_target_z_offset': '1.0'},
        'ModelProcessing': {'desired_model_height': '0'}
    }
    for base_sec, defaults in default_structure.items():
        if base_sec not in blender_cfg:
            print(f"Info: Section '{base_sec}' was completely missing and will be filled with minimal defaults for '{anim_set_info['spritesheet_base_name']}'.")
            blender_cfg[base_sec] = defaults

    try:
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            blender_cfg.write(f)
        print(f"Blender config for '{anim_set_info['spritesheet_base_name']}' generated: {temp_config_path}")
    except IOError as e:
        print(f"ERROR writing temporary Blender configuration file '{temp_config_path}': {e}")

def assemble_spritesheet(spritesheet_base_name, frames_input_dir, spritesheet_output_dir, main_config_ignored_for_now):
    print(f"\nCreating spritesheet for {spritesheet_base_name} (order: rows=angles, columns=AnimFrames)...")
    frame_files_pattern = os.path.join(frames_input_dir, "angle_*.png")
    frame_files_list = glob.glob(frame_files_pattern)

    if not frame_files_list:
        print(f"Error: No rendered frames found at '{frame_files_pattern}' for {spritesheet_base_name}."); return None

    print(f"{len(frame_files_list)} frames found for {spritesheet_base_name}.")

    parsed_frames_info = []
    max_angle_idx = -1
    max_anim_idx = -1

    for f_path in frame_files_list:
        f_name = os.path.basename(f_path)
        try:
            parts = f_name[:-4].split('_')
            if len(parts) == 4 and parts[0] == "angle" and parts[2] == "animframe":
                angle_idx = int(parts[1])
                anim_idx = int(parts[3])
                parsed_frames_info.append({'path': f_path, 'angle_idx': angle_idx, 'anim_idx': anim_idx})
                if angle_idx > max_angle_idx: max_angle_idx = angle_idx
                if anim_idx > max_anim_idx: max_anim_idx = anim_idx
            else:
                print(f"Warning: Unexpected frame filename format skipped: {f_name}")
        except (ValueError, IndexError) as e:
            print(f"Warning: Could not parse indices from filename '{f_name}': {e}")
            continue

    if not parsed_frames_info:
        print(f"Error: No valid frame filenames found in directory {frames_input_dir} after parsing."); return None

    parsed_frames_info.sort(key=lambda x: (x['angle_idx'], x['anim_idx']))

    try:
        first_frame_path = parsed_frames_info[0]['path']
        with Image.open(first_frame_path) as first_frame_img:
            sprite_width, sprite_height = first_frame_img.size
    except Exception as e:
        print(f"Error opening first frame '{first_frame_path}': {e}"); return None

    num_rows = max_angle_idx + 1
    num_columns = max_anim_idx + 1

    if num_columns <= 0 or num_rows <= 0:
        print(f"Error: Spritesheet dimensions invalid (columns={num_columns}, rows={num_rows}). "
              f"Max Angle Idx (rows): {max_angle_idx}, Max Anim Idx (columns): {max_anim_idx}."); return None

    spritesheet_width_px = num_columns * sprite_width
    spritesheet_height_px = num_rows * sprite_height

    spritesheet = Image.new('RGBA', (spritesheet_width_px, spritesheet_height_px), (0, 0, 0, 0))
    print(f"Creating spritesheet ({spritesheet_base_name}): {num_rows} rows (angles) x {num_columns} columns (animation frames). "
          f"Single frame: {sprite_width}x{sprite_height}px. Total size: {spritesheet_width_px}x{spritesheet_height_px}px.")

    for frame_info in parsed_frames_info:
        try:
            with Image.open(frame_info['path']) as frame_img:
                img_to_paste = frame_img if frame_img.mode == 'RGBA' else frame_img.convert('RGBA')
                x_offset = frame_info['anim_idx'] * sprite_width
                y_offset = frame_info['angle_idx'] * sprite_height
                spritesheet.paste(img_to_paste, (x_offset, y_offset), mask=img_to_paste)
        except FileNotFoundError:
            print(f"Error: Frame file not found during assembly: {frame_info['path']}")
            continue
        except Exception as e:
            print(f"Error processing frame {frame_info['path']} for spritesheet: {e}")

    output_filename_base = f"{spritesheet_base_name.lower().replace(' ', '_')}_spritesheet_angle_rows"
    output_path_png = os.path.join(spritesheet_output_dir, f"{output_filename_base}.png")
    output_path_json = os.path.join(spritesheet_output_dir, f"{output_filename_base}.json")

    try:
        spritesheet.save(output_path_png)
        print(f"Spritesheet for {spritesheet_base_name} saved: {output_path_png}")

        metadata = {
            "image_file": os.path.basename(output_path_png),
            "layout_description": "Rows are rotation angles (angle_idx increasing), columns are animation poses (anim_idx increasing).",
            "total_angles_or_rows": num_rows,
            "total_animation_frames_per_angle_or_columns": num_columns,
            "sprite_width_px": sprite_width,
            "sprite_height_px": sprite_height,
            "source_model_and_animation_name": spritesheet_base_name,
        }
        with open(output_path_json, 'w', encoding='utf-8') as f_json:
            json.dump(metadata, f_json, indent=4)
        print(f"Metadata for {spritesheet_base_name} saved: {output_path_json}")
        return output_path_png
    except Exception as e:
        print(f"Error saving spritesheet/metadata for {spritesheet_base_name}: {e}"); return None

def update_spritesheet_manifest(output_spritesheet_dir_):
    print("\nUpdating spritesheet manifest...")
    manifest_data = []
    json_file_pattern = os.path.join(output_spritesheet_dir_, "*_spritesheet_angle_rows.json")
    found_json_files = glob.glob(json_file_pattern)
    print(f"Searching for individual metadata JSONs with pattern: {json_file_pattern}")
    print(f"Found JSON files for manifest: {len(found_json_files)}")

    for f_json_path in found_json_files:
        if os.path.basename(f_json_path) == "manifest_spritesheets.json":
            print(f"  -> Skipping manifest file itself: {f_json_path}")
            continue

        print(f"  Processing metadata file: {f_json_path}")
        try:
            with open(f_json_path, 'r', encoding='utf-8') as f_json:
                data = json.load(f_json)
                if "source_model_and_animation_name" in data and "image_file" in data:
                    manifest_data.append({
                        "model_and_animation_name": data.get("source_model_and_animation_name"),
                        "spritesheet_file": data.get("image_file"),
                        "metadata_file": os.path.basename(f_json_path)
                    })
                    print(f"    -> '{data.get('source_model_and_animation_name')}' added to manifest.")
                else:
                    print(f"    WARNING: Missing keys ('source_model_and_animation_name' or 'image_file') in {f_json_path}. Skipping.")
        except json.JSONDecodeError as e:
            print(f"    WARNING: Invalid JSON in {f_json_path}: {e}. Skipping.")
        except Exception as e:
            print(f"    WARNING: Could not process metadata file {f_json_path}: {e}. Skipping.")

    manifest_file_path = os.path.join(output_spritesheet_dir_, "manifest_spritesheets.json")
    try:
        manifest_data_sorted = sorted(manifest_data, key=lambda x: x.get("model_and_animation_name", "").lower())

        with open(manifest_file_path, 'w', encoding='utf-8') as f_manifest:
            json.dump(manifest_data_sorted, f_manifest, indent=4)

        if not manifest_data_sorted:
            print(f"Spritesheet manifest updated/created: {manifest_file_path}, but NO entries found.")
        else:
            print(f"Spritesheet manifest updated/created: {manifest_file_path} with {len(manifest_data_sorted)} entries.")

    except IOError as e:
        print(f"ERROR writing spritesheet manifest '{manifest_file_path}': {e}")
    except Exception as e:
        print(f"ERROR updating spritesheet manifest: {e}")

def main_orchestrator():
    print("--- Animated 2D Spritesheet Generator (Local Version) ---")
    setup_directories()
    main_cfg = load_main_config()
    selected_animation_sets = find_model_sets(INPUT_DIR_ROOT)

    if not selected_animation_sets:
        print("No model-animation sets selected or found for processing. Program will exit.")
        sys.exit(0)

    successful_spritesheets_count = 0
    for anim_set in selected_animation_sets:
        processing_name = anim_set['spritesheet_base_name']
        print(f"\n--- Processing: {processing_name} ---")
        anim_temp_frames_dir = anim_set['output_subdir_frames']

        if os.path.exists(anim_temp_frames_dir):
            print(f"Cleaning up old temporary frame directory: {anim_temp_frames_dir}")
            try:
                shutil.rmtree(anim_temp_frames_dir)
            except OSError as e:
                print(f"Error deleting {anim_temp_frames_dir}: {e}. Attempting to continue anyway.")
        try:
            os.makedirs(anim_temp_frames_dir, exist_ok=True)
            print(f"Temporary frame directory for {processing_name} created/emptied: {anim_temp_frames_dir}")
        except OSError as e:
            print(f"ERROR: Could not create temporary frame directory: {anim_temp_frames_dir}: {e}"); continue

        temp_blender_config_path = os.path.join(anim_temp_frames_dir, f"blender_cfg_{processing_name}.ini")
        generate_blender_config_ini(anim_set, main_cfg, temp_blender_config_path)

        blender_executable = main_cfg['Blender']['blender_executable_path']
        cmd = [
            blender_executable,
            '--background',
            '--python', BLENDER_ANIM_SCRIPT_PATH,
            '--',
            '--config_path', temp_blender_config_path
        ]
        print(f"\nStarting Blender rendering process for {processing_name}...")

        blender_process_return_code = -1
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            process_result = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
            blender_process_return_code = process_result.returncode

            print(f"\n--- Blender Output for {processing_name} (Return Code: {blender_process_return_code}) ---")
            if process_result.stdout:
                print("--- Blender STDOUT ---")
                lines_to_show = []
                important_keywords = ["error", "warn", "fail", "crit", "traceback", "saved:", "rendering complete", "exit-code", "version:", "configuration loaded", "importing", "root object", "material", "camera and light", "render aspect", "ortho scale", "animation from frame"]
                progress_markers = ["fra:", "mem:", "time:", "path tracing tile", "syncing", "rendering "]

                for line in process_result.stdout.splitlines():
                    line_lower = line.lower().strip()
                    if any(kw in line_lower for kw in important_keywords) or not any(pm in line_lower for pm in progress_markers):
                        lines_to_show.append(line)
                    elif "saved:" in line_lower and ".png" in line_lower:
                        lines_to_show.append(f"  >> {line.strip()}")

                if not lines_to_show and process_result.stdout.strip():
                    lines_to_show = process_result.stdout.splitlines()[:20] + ["... (Rest truncated)"] if len(process_result.stdout.splitlines()) > 20 else process_result.stdout.splitlines()
                for l_to_show in lines_to_show: print(l_to_show)

            if process_result.stderr:
                print(f"\n--- Blender STDERR for {processing_name} (if any) ---")
                for line in process_result.stderr.splitlines(): print(line)

            if blender_process_return_code != 0:
                print(f"Error: Blender process for {processing_name} failed with exit code {blender_process_return_code}.")
            else:
                print(f"Blender rendering for {processing_name} apparently completed successfully (Return Code 0).")

        except FileNotFoundError:
            print(f"Error: Blender not found: '{blender_executable}'. Please check path in config.ini."); continue
        except Exception as e:
            print(f"Unexpected error while running Blender for {processing_name}: {e}"); continue

        if blender_process_return_code == 0:
            spritesheet_path_png = assemble_spritesheet(
                anim_set['spritesheet_base_name'],
                anim_temp_frames_dir,
                anim_set['output_spritesheet_dir'],
                main_cfg
            )
            if spritesheet_path_png:
                successful_spritesheets_count += 1
                try:
                    print(f"\nCleaning up temporary files for {processing_name}...")
                    shutil.rmtree(anim_temp_frames_dir)
                    print(f"Temporary directory {anim_temp_frames_dir} removed.")
                except Exception as e_clean:
                    print(f"Error cleaning up temporary files for {processing_name}: {e_clean}")
            else:
                print(f"\nSpritesheet creation for {processing_name} failed. Temporary files in {anim_temp_frames_dir} will be kept for debugging.")
        else:
            print(f"\nSkipping spritesheet creation for {processing_name} due to Blender errors. Temporary files in {anim_temp_frames_dir} will be kept for debugging.")

    if successful_spritesheets_count > 0:
        update_spritesheet_manifest(OUTPUT_DIR_SPRITESHEETS)
    else:
        print("\nNo spritesheets created successfully. Manifest will not be updated.")

    print("\n--- All selected model-animation sets processed ---")

if __name__ == "__main__":
    main_orchestrator()