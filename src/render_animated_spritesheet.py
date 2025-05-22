import bpy
import os
import sys
import math
import argparse
import configparser
import addon_utils
import traceback
import mathutils

def ensure_addon_enabled(addon_module_name):
    module_is_known = False
    if hasattr(addon_utils, 'bpy_module_specs'):
        for mod_spec in addon_utils.bpy_module_specs:
            if mod_spec.name == addon_module_name:
                module_is_known = True; break
    else:
        for mod in addon_utils.modules():
            if mod.__name__ == addon_module_name:
                module_is_known = True; break

    if not module_is_known:
        print(f"CRITICAL: Add-on module '{addon_module_name}' is not known/found by Blender.")
        return False

    try:
        _, enabled_default = addon_utils.check(addon_module_name)
    except Exception as e:
        print(f"Error during addon_utils.check for '{addon_module_name}': {e}"); return False

    operator_present = False
    if addon_module_name == "io_scene_obj": operator_present = hasattr(bpy.ops.import_scene, 'obj')
    elif addon_module_name == "io_scene_fbx": operator_present = hasattr(bpy.ops.import_scene, 'fbx')
    else: operator_present = True

    if enabled_default and operator_present:
        return True

    print(f"Add-on '{addon_module_name}' (Status: {'enabled' if enabled_default else 'disabled'}, Operator: {'present' if operator_present else 'missing'}) will be (re)activated...")
    try:
        bpy.ops.preferences.addon_enable(module=addon_module_name)
        bpy.utils.refresh_script_paths()

        _, is_now_enabled = addon_utils.check(addon_module_name)
        if not is_now_enabled:
            print(f"ERROR: Add-on '{addon_module_name}' could NOT be confirmed as enabled after enable attempt.")
            return False

        if addon_module_name == "io_scene_obj" and not hasattr(bpy.ops.import_scene, 'obj'):
            print(f"ERROR AFTER ACTIVATION: Operator 'bpy.ops.import_scene.obj' for '{addon_module_name}' is still missing!")
            return False
        elif addon_module_name == "io_scene_fbx" and not hasattr(bpy.ops.import_scene, 'fbx'):
            print(f"ERROR AFTER ACTIVATION: Operator 'bpy.ops.import_scene.fbx' for '{addon_module_name}' is still missing!")
            return False

        print(f"Add-on '{addon_module_name}' successfully activated/confirmed.")
        return True

    except Exception as e:
        print(f"Serious error during bpy.ops.preferences.addon_enable for '{addon_module_name}':")
        traceback.print_exc(); return False

def clear_scene():
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.select_all(action='SELECT')
    if bpy.context.selected_objects:
        bpy.ops.object.delete()

    for block_type in [bpy.data.meshes, bpy.data.materials, bpy.data.textures,
                       bpy.data.images, bpy.data.lights, bpy.data.cameras,
                       bpy.data.armatures, bpy.data.actions, bpy.data.worlds, bpy.data.node_groups]:
        for block in block_type:
            if block.users == 0:
                try: block_type.remove(block)
                except: pass

    empties_to_remove = [obj for obj in bpy.data.objects if obj.type == 'EMPTY' and obj.users == 0]
    for empty in empties_to_remove:
        try: bpy.data.objects.remove(empty, do_unlink=True)
        except: pass
    print("Scene cleared.")

def import_fbx(filepath, config_options=None):
    if not ensure_addon_enabled("io_scene_fbx"):
        raise RuntimeError(f"FBX Importer 'io_scene_fbx' could not be activated. Import of '{filepath}' aborted.")

    initial_objects = set(bpy.context.scene.objects)
    import_settings = {
        'filepath': filepath,
        'use_prepost_rot': True,
        'automatic_bone_orientation': True,
    }
    if config_options:
        pass

    try:
        bpy.ops.import_scene.fbx(**import_settings)
    except RuntimeError as e:
        print(f"RuntimeError during bpy.ops.import_scene.fbx for '{filepath}': {e}"); return [], None, None
    except AttributeError:
        print(f"AttributeError: Operator 'bpy.ops.import_scene.fbx' missing. Add-on 'io_scene_fbx' problem."); raise

    imported_objects = [obj for obj in bpy.context.scene.objects if obj not in initial_objects]
    if not imported_objects:
        print(f"Warning: No objects imported from FBX: {filepath}"); return [], None, None

    armature = next((obj for obj in imported_objects if obj.type == 'ARMATURE'), None)
    mesh_objects = [obj for obj in imported_objects if obj.type == 'MESH']

    if not armature: print(f"Warning: No armature found in FBX '{filepath}'.")
    if not mesh_objects: print(f"Warning: No mesh objects found in FBX '{filepath}'.")

    primary_mesh = None
    if armature and mesh_objects:
        for m in mesh_objects:
            if m.parent == armature: primary_mesh = m; break
            if any(mod.type == 'ARMATURE' and mod.object == armature for mod in m.modifiers):
                primary_mesh = m; break
        if not primary_mesh and mesh_objects: primary_mesh = mesh_objects[0]
    elif mesh_objects: primary_mesh = mesh_objects[0]

    print(f"Imported FBX: {filepath}. Armature: {armature.name if armature else 'None'}, Primary Mesh: {primary_mesh.name if primary_mesh else 'None'}")
    return imported_objects, armature, primary_mesh

def import_obj_for_materials(filepath):
    if not ensure_addon_enabled("io_scene_obj"):
        print(f"WARNING: OBJ Importer 'io_scene_obj' could not be activated. Material import from '{filepath}' skipped.")
        return {}, []

    initial_objects = set(bpy.context.scene.objects)
    initial_materials = set(bpy.data.materials)
    try:
        bpy.ops.import_scene.obj(filepath=filepath, use_image_search=True)
    except RuntimeError as e: print(f"RuntimeError during bpy.ops.import_scene.obj for '{filepath}': {e}"); return {}, []
    except AttributeError: print(f"AttributeError: Operator 'bpy.ops.import_scene.obj' missing."); return {}, []

    imported_obj_objects = [obj for obj in bpy.context.scene.objects if obj not in initial_objects]
    loaded_materials_from_obj = set()
    for obj in imported_obj_objects:
        for slot in obj.material_slots:
            if slot.material:
                loaded_materials_from_obj.add(slot.material)

    newly_loaded_materials = {mat.name: mat for mat in loaded_materials_from_obj if mat not in initial_materials}

    print(f"Imported OBJ for materials: {filepath}. {len(newly_loaded_materials)} new materials found. {len(imported_obj_objects)} temporary objects imported.")
    return newly_loaded_materials, imported_obj_objects

def import_fbx_for_materials(filepath):
    if not ensure_addon_enabled("io_scene_fbx"):
        print(f"WARNING: FBX Importer 'io_scene_fbx' for materials not activatable. Import from '{filepath}' skipped.")
        return {}, []

    print(f"Importing FBX for materials: {filepath}")
    initial_objects = set(bpy.context.scene.objects)
    initial_materials = set(bpy.data.materials)
    try:
        bpy.ops.import_scene.fbx(filepath=filepath, use_prepost_rot=True, use_anim=False)
    except RuntimeError as e: print(f"RuntimeError during import of material FBX '{filepath}': {e}"); return {}, []
    except AttributeError: print(f"AttributeError: Operator 'bpy.ops.import_scene.fbx' for material FBX missing."); return {}, []

    imported_fbx_objects = [obj for obj in bpy.context.scene.objects if obj not in initial_objects]
    loaded_materials_from_fbx = set()
    for obj in imported_fbx_objects:
        for slot in obj.material_slots:
            if slot.material:
                loaded_materials_from_fbx.add(slot.material)

    newly_loaded_materials = {mat.name: mat for mat in loaded_materials_from_fbx if mat not in initial_materials}

    print(f"Imported material FBX '{filepath}'. {len(newly_loaded_materials)} new materials found. {len(imported_fbx_objects)} temporary objects imported.")
    return newly_loaded_materials, imported_fbx_objects

def transfer_materials(target_mesh, source_materials_dict):
    if not target_mesh or target_mesh.type != 'MESH':
        print("Error: Target for material transfer is not a valid mesh object."); return
    if not source_materials_dict:
        print("Warning: No source materials for transfer. No changes to target mesh materials."); return

    print(f"Attempting to transfer materials to '{target_mesh.name}'. Available source materials: {list(source_materials_dict.keys())}")

    if not target_mesh.data.materials:
        print(f"Target mesh '{target_mesh.name}' has no material slots. Adding first slot.")
        first_source_mat_name = list(source_materials_dict.keys())[0]
        target_mesh.data.materials.append(source_materials_dict[first_source_mat_name])
        print(f"Material '{first_source_mat_name}' assigned to new slot on '{target_mesh.name}'.")
        return

    for slot_idx, slot in enumerate(target_mesh.material_slots):
        original_mat_name_in_slot = slot.material.name if slot.material else f"Slot_{slot_idx}_Empty"
        assigned_material = False

        current_slot_mat_name_key = slot.material.name_full if slot.material else None

        if current_slot_mat_name_key and current_slot_mat_name_key in source_materials_dict:
            new_mat = source_materials_dict[current_slot_mat_name_key]
            if slot.material != new_mat: slot.material = new_mat
            print(f"Material '{new_mat.name}' (exact match on '{current_slot_mat_name_key}') assigned to Slot {slot_idx} ('{original_mat_name_in_slot}') on '{target_mesh.name}'.")
            assigned_material = True
        else:
            base_name_in_slot = slot.material.name.split('.')[0] if slot.material else None
            if base_name_in_slot:
                for src_name, src_mat in source_materials_dict.items():
                    if src_name.split('.')[0].lower() == base_name_in_slot.lower():
                        if slot.material != src_mat: slot.material = src_mat
                        print(f"Material '{src_mat.name}' (base name match on '{base_name_in_slot}') assigned to Slot {slot_idx} ('{original_mat_name_in_slot}') on '{target_mesh.name}'.")
                        assigned_material = True; break

        if not assigned_material and slot_idx == 0:
            first_source_mat_name = list(source_materials_dict.keys())[0]
            fallback_mat = source_materials_dict[first_source_mat_name]
            if slot.material != fallback_mat: slot.material = fallback_mat
            print(f"WARNING: No match for Slot {slot_idx} ('{original_mat_name_in_slot}'). First available source material '{fallback_mat.name}' assigned as fallback.")
            assigned_material = True

        if not assigned_material:
            print(f"WARNING: For Slot {slot_idx} ('{original_mat_name_in_slot}') on '{target_mesh.name}', no matching material could be found and assigned.")

def get_hierarchy_root(objects_list):
    valid_objects = [obj for obj in objects_list if obj and obj.name in bpy.context.scene.objects]
    if not valid_objects: return None

    roots = [obj for obj in valid_objects if obj.parent is None or obj.parent not in valid_objects]

    if not roots and valid_objects: return valid_objects[0]
    if len(roots) == 1: return roots[0]

    if len(roots) > 1:
        print(f"Multiple potential root objects found: {[r.name for r in roots]}. Attempting best selection...")
        armature_root = next((r for r in roots if r.type == 'ARMATURE'), None)
        if armature_root: print(f"  -> Armature '{armature_root.name}' chosen as root."); return armature_root

        empty_roots_with_children = [r for r in roots if r.type == 'EMPTY' and any(child in valid_objects for child in r.children_recursive)]
        if len(empty_roots_with_children) == 1:
            print(f"  -> Empty '{empty_roots_with_children[0].name}' with children chosen as root."); return empty_roots_with_children[0]

        roots.sort(key=lambda r: len([c for c in r.children_recursive if c in valid_objects]), reverse=True)
        if roots: print(f"  -> Root '{roots[0].name}' chosen by child count."); return roots[0]

    return valid_objects[0] if valid_objects else None

def prepare_model(root_obj, scene):
    if not root_obj or root_obj.name not in scene.objects:
        print(f"Error: Root object ('{root_obj.name if root_obj else 'None'}') not found for preparation."); return

    bpy.ops.object.select_all(action='DESELECT')

    def select_recursive(obj_to_select):
        if obj_to_select and obj_to_select.name in scene.objects:
            try: obj_to_select.select_set(True)
            except ReferenceError: print(f"Warning: Object {obj_to_select.name if obj_to_select else 'Unknown'} no longer exists."); return
            for child in obj_to_select.children: select_recursive(child)

    select_recursive(root_obj)
    if root_obj.name in scene.objects:
        if scene.view_layers[0].objects.active != root_obj:
            try: scene.view_layers[0].objects.active = root_obj
            except Exception as e: print(f"Warning: Could not set active object to {root_obj.name}: {e}")
    else:
        print(f"Warning: Root object {root_obj.name} no longer in scene after recursive selection, cannot apply transform.")
        return

    if bpy.context.selected_objects and bpy.context.object:
        try:
            if bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            print(f"Transformations (Loc, Rot, Scale) applied to '{bpy.context.object.name}' and its selected hierarchy.")
        except RuntimeError as e: print(f"Warning: Could not apply transformations to '{bpy.context.object.name}': {e}")
    else: print(f"Warning: No objects selected or no active object for transform application (Root: '{root_obj.name}').")

    min_coords, max_coords = [float('inf')] * 3, [float('-inf')] * 3
    has_visible_geom = False

    meshes_for_bounds = []
    def get_visible_meshes_recursive(obj_node):
        if obj_node and obj_node.name in scene.objects and obj_node.visible_get(view_layer=scene.view_layers[0]):
            if obj_node.type == 'MESH' and obj_node.data and obj_node.data.vertices:
                meshes_for_bounds.append(obj_node)
            for child in obj_node.children: get_visible_meshes_recursive(child)

    if root_obj and root_obj.name in scene.objects:
        get_visible_meshes_recursive(root_obj)

    if not meshes_for_bounds:
        print(f"Warning: No visible mesh objects found in hierarchy of '{root_obj.name}' for bounds calculation.")
        if root_obj and root_obj.name in scene.objects and root_obj.type == 'MESH' and root_obj.data:
            bpy.ops.object.select_all(action='DESELECT'); root_obj.select_set(True)
            if scene.view_layers[0].objects.active != root_obj: scene.view_layers[0].objects.active = root_obj
            try:
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                root_obj.location = (0,0,0)
                print(f"Fallback: Origin of '{root_obj.name}' set to geometry bounds and centered at world origin.")
            except RuntimeError as e: print(f"Fallback origin_set for '{root_obj.name}' failed: {e}")
        return

    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj_mesh in meshes_for_bounds:
        obj_eval = obj_mesh.evaluated_get(depsgraph)
        try: mesh_eval_data = obj_eval.to_mesh()
        except RuntimeError: continue
        if not mesh_eval_data or not mesh_eval_data.vertices:
            if mesh_eval_data: obj_eval.to_mesh_clear();
            continue

        has_visible_geom = True
        for v in mesh_eval_data.vertices:
            world_co = obj_mesh.matrix_world @ v.co
            for i in range(3):
                min_coords[i] = min(min_coords[i], world_co[i])
                max_coords[i] = max(max_coords[i], world_co[i])
        obj_eval.to_mesh_clear()

    if has_visible_geom:
        center_x = (min_coords[0] + max_coords[0]) / 2
        center_y = (min_coords[1] + max_coords[1]) / 2
        base_z = min_coords[2]

        original_cursor_location = scene.cursor.location.copy()
        scene.cursor.location = mathutils.Vector((center_x, center_y, base_z))

        bpy.ops.object.select_all(action='DESELECT')
        if root_obj.name in scene.objects:
            root_obj.select_set(True)
            if scene.view_layers[0].objects.active != root_obj:
                scene.view_layers[0].objects.active = root_obj

            if bpy.context.selected_objects and bpy.context.object == root_obj:
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
                root_obj.location = mathutils.Vector((0,0,0))
                print(f"Origin of '{root_obj.name}' set to hierarchy base ({center_x:.2f}, {center_y:.2f}, {base_z:.2f}) and object moved to world origin.")
            else: print(f"Warning: '{root_obj.name}' could not be selected/activated for origin setting.")
        else: print(f"Warning: Root object '{root_obj.name}' no longer in scene for final positioning.")

        scene.cursor.location = original_cursor_location
    else:
        print(f"Warning: No geometry found for bounds calculation for '{root_obj.name}'. Model not centered via bounds.")

def setup_camera_and_lighting(config_camera_section, scene_res_x, scene_res_y, root_for_bounds_calc):
    print("Starting camera and light setup...")
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer

    cam_dist = config_camera_section.getfloat('camera_distance', 7.0)
    cam_elev_deg = config_camera_section.getfloat('camera_elevation_degrees', 20.0)
    cam_target_z_offset = config_camera_section.getfloat('camera_target_z_offset', 1.0)

    ortho_padding_factor = config_camera_section.getfloat('ortho_scale_padding_factor', 1.15)
    ortho_fallback_scale = config_camera_section.getfloat('ortho_scale_fallback', 4.0)

    key_light_energy = config_camera_section.getfloat('key_light_energy', 3.0)
    key_light_softness_deg = config_camera_section.getfloat('key_light_angle_softness', 10.0)
    fill_light_energy = config_camera_section.getfloat('fill_light_energy', 1.5)
    fill_light_softness_deg = config_camera_section.getfloat('fill_light_angle_softness', 15.0)

    ambient_light_color_str = config_camera_section.get('ambient_light_color', '0.1,0.1,0.1,1.0')
    ambient_light_strength = config_camera_section.getfloat('ambient_light_strength', 0.5)

    try:
        ambient_color_parts = [float(c.strip()) for c in ambient_light_color_str.split(',')]
        if len(ambient_color_parts) == 4:
            ambient_light_color = tuple(ambient_color_parts)
        else:
            print(f"WARNING: ambient_light_color ('{ambient_light_color_str}') does not have 4 parts. Using fallback.")
            ambient_light_color = (0.1, 0.1, 0.1, 1.0)
    except ValueError:
        print(f"WARNING: ambient_light_color ('{ambient_light_color_str}') could not be parsed. Using fallback.")
        ambient_light_color = (0.1, 0.1, 0.1, 1.0)

    target_base_location = mathutils.Vector((0,0,0))
    if root_for_bounds_calc and root_for_bounds_calc.name in scene.objects:
        target_base_location = root_for_bounds_calc.location.copy()

    target_actual_location = mathutils.Vector((target_base_location.x, target_base_location.y, target_base_location.z + cam_target_z_offset))

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=target_actual_location)
    cam_target = bpy.context.object
    cam_target.name = "SpriteLookAtTarget"

    bpy.ops.object.camera_add(location=(0,0,0))
    cam_obj = bpy.context.object
    cam_obj.name = "SpriteRenderCam"
    scene.camera = cam_obj
    cam_data = cam_obj.data
    cam_data.type = 'ORTHO'

    elev_rad = math.radians(cam_elev_deg)
    cam_x = target_actual_location.x
    cam_y = target_actual_location.y - cam_dist * math.cos(elev_rad)
    cam_z = target_actual_location.z + cam_dist * math.sin(elev_rad)
    cam_obj.location = (cam_x, cam_y, cam_z)

    track_constr = cam_obj.constraints.new(type='TRACK_TO')
    track_constr.target = cam_target
    track_constr.track_axis = 'TRACK_NEGATIVE_Z'
    track_constr.up_axis = 'UP_Y'

    effective_ortho_scale = ortho_fallback_scale
    model_width_world, model_height_world = 0.0, 0.0

    if root_for_bounds_calc and root_for_bounds_calc.name in scene.objects:
        meshes_for_scale_calc = []
        def get_visible_meshes_recursive_for_scale(obj_node):
            if obj_node and obj_node.name in scene.objects and obj_node.visible_get(view_layer=view_layer):
                if obj_node.type == 'MESH' and obj_node.data and obj_node.data.vertices:
                    meshes_for_scale_calc.append(obj_node)
                for child in obj_node.children:
                    get_visible_meshes_recursive_for_scale(child)

        get_visible_meshes_recursive_for_scale(root_for_bounds_calc)

        if meshes_for_scale_calc:
            min_coords_cam, max_coords_cam = [float('inf')] * 3, [float('-inf')] * 3
            has_geom_for_scale = False
            depsgraph = bpy.context.evaluated_depsgraph_get()

            for m_obj in meshes_for_scale_calc:
                obj_eval = m_obj.evaluated_get(depsgraph)
                try:
                    mesh_eval_data = obj_eval.to_mesh()
                except RuntimeError:
                    if obj_eval.is_evaluated: obj_eval.to_mesh_clear()
                    continue

                if not mesh_eval_data or not mesh_eval_data.vertices:
                    if mesh_eval_data : obj_eval.to_mesh_clear()
                    continue

                has_geom_for_scale = True
                for v_local in mesh_eval_data.vertices:
                    v_world = m_obj.matrix_world @ v_local.co
                    for i in range(3):
                        min_coords_cam[i] = min(min_coords_cam[i], v_world[i])
                        max_coords_cam[i] = max(max_coords_cam[i], v_world[i])
                obj_eval.to_mesh_clear()

            if has_geom_for_scale:
                model_width_world = max_coords_cam[0] - min_coords_cam[0]
                model_depth_world = max_coords_cam[1] - min_coords_cam[1]
                model_height_world = max_coords_cam[2] - min_coords_cam[2]
                print(f"DEBUG Camera Scale: Raw World Dimensions (W,D,H): {model_width_world:.3f}, {model_depth_world:.3f}, {model_height_world:.3f}")

                if model_width_world < 1e-4 and model_height_world < 1e-4:
                    print(f"WARNING: Model dimensions for camera scale are minimal/null. Using fallback ortho scale: {ortho_fallback_scale}")
                    effective_ortho_scale = ortho_fallback_scale
                else:
                    render_aspect_ratio = scene_res_x / scene_res_y if scene_res_y != 0 else 1.0

                    scaled_half_width = (model_width_world / render_aspect_ratio) / 2.0
                    half_height = model_height_world / 2.0

                    if scaled_half_width >= half_height:
                        effective_ortho_scale = scaled_half_width
                    else:
                        effective_ortho_scale = half_height

                    effective_ortho_scale *= ortho_padding_factor

                    min_practical_ortho = 0.01
                    if effective_ortho_scale < min_practical_ortho and effective_ortho_scale > 1e-5:
                        print(f"WARNING: Calculated ortho scale ({effective_ortho_scale:.4f}) very small. Raised to {min_practical_ortho}.")
                        effective_ortho_scale = min_practical_ortho
                    elif effective_ortho_scale <= 1e-5:
                        print(f"WARNING: Ortho scale is zero/negative ({effective_ortho_scale:.4f}). Fallback to {ortho_fallback_scale}.")
                        effective_ortho_scale = ortho_fallback_scale
            else:
                print(f"WARNING: No visible geometry in '{root_for_bounds_calc.name}' for camera scaling found. Fallback ortho scale: {ortho_fallback_scale}")
        else:
            print(f"WARNING: No mesh objects in '{root_for_bounds_calc.name}' for camera scaling found. Fallback ortho scale: {ortho_fallback_scale}")
    else:
        print(f"WARNING: No (valid) root object passed for camera scaling. Fallback ortho scale: {ortho_fallback_scale}")

    cam_data.ortho_scale = effective_ortho_scale
    print(f"Model dimensions for camera (W World: {model_width_world:.2f}, H World: {model_height_world:.2f}). "
          f"Render aspect: {scene_res_x/scene_res_y if scene_res_y!=0 else 1:.2f}. "
          f"Final ortho scale: {cam_data.ortho_scale:.3f}")

    cam_data.clip_start = 0.01
    cam_data.clip_end = cam_dist + max(model_width_world, model_height_world) * 2 + 10

    bpy.ops.object.light_add(type='SUN', align='WORLD', location=(0,0,0))
    key_light = bpy.context.object
    key_light.name = "KeySunLight"
    key_light.data.energy = key_light_energy
    key_light.data.angle = math.radians(key_light_softness_deg)
    key_light.rotation_euler = (math.radians(45), math.radians(-30), math.radians(-45))

    bpy.ops.object.light_add(type='SUN', align='WORLD', location=(0,0,0))
    fill_light = bpy.context.object
    fill_light.name = "FillSunLight"
    fill_light.data.energy = fill_light_energy
    fill_light.data.angle = math.radians(fill_light_softness_deg)
    fill_light.rotation_euler = (math.radians(30), math.radians(45), math.radians(30))

    if not scene.world:
        scene.world = bpy.data.worlds.new("SpriteRenderWorld")
        print("New world 'SpriteRenderWorld' created.")

    scene.world.use_nodes = True
    world_tree = scene.world.node_tree

    bg_node = None
    if 'Background' in world_tree.nodes:
        bg_node = world_tree.nodes['Background']
    else:
        try:
            bg_node_candidates = [n for n in world_tree.nodes if n.type == 'BACKGROUND']
            if bg_node_candidates: bg_node = bg_node_candidates[0]
        except: pass

    if not bg_node:
        bg_node = world_tree.nodes.new(type='ShaderNodeBackground')
        print("New Background node added to world.")

    world_output_node = None
    if 'World Output' in world_tree.nodes:
        world_output_node = world_tree.nodes['World Output']
    else:
        output_node_candidates = [n for n in world_tree.nodes if n.type == 'OUTPUT_WORLD']
        if output_node_candidates: world_output_node = output_node_candidates[0]

    if not world_output_node:
        world_output_node = world_tree.nodes.new(type='ShaderNodeOutputWorld')
        print("New World Output node added to world.")

    is_linked = False
    if bg_node and world_output_node and 'Surface' in world_output_node.inputs:
        for link in world_tree.links:
            if link.from_node == bg_node and link.to_node == world_output_node and link.to_socket.name == 'Surface':
                is_linked = True; break
        if not is_linked:
            world_tree.links.new(bg_node.outputs['Background'], world_output_node.inputs['Surface'])
            print("Background node connected to World Output.")

    if bg_node:
        if 'Color' in bg_node.inputs: bg_node.inputs['Color'].default_value = ambient_light_color
        if 'Strength' in bg_node.inputs: bg_node.inputs['Strength'].default_value = ambient_light_strength
        print(f"World background lighting set: Color {ambient_light_color}, Strength {ambient_light_strength}")
    else:
        print("WARNING: Could not set up Background node for world lighting.")

    print("Camera and light setup completed.")
    return cam_obj, cam_target

def get_selection_bounding_box_world(objects_to_measure, depsgraph):
    min_coords = mathutils.Vector((float('inf'), float('inf'), float('inf')))
    max_coords = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))
    has_geom = False

    for obj in objects_to_measure:
        if not obj or obj.type != 'MESH' or not obj.data:
            continue

        obj_eval = obj.evaluated_get(depsgraph)
        try:
            mesh_eval_data = obj_eval.to_mesh()
        except RuntimeError:
            if hasattr(obj_eval, 'to_mesh_clear'): obj_eval.to_mesh_clear()
            continue

        if not mesh_eval_data or not mesh_eval_data.vertices:
            if mesh_eval_data and hasattr(obj_eval, 'to_mesh_clear'): obj_eval.to_mesh_clear()
            continue

        has_geom = True
        for v_local in mesh_eval_data.vertices:
            v_world = obj.matrix_world @ v_local.co
            for i in range(3):
                min_coords[i] = min(min_coords[i], v_world[i])
                max_coords[i] = max(max_coords[i], v_world[i])

        if hasattr(obj_eval, 'to_mesh_clear'):
            obj_eval.to_mesh_clear()

    return (min_coords, max_coords) if has_geom else (None, None)

def scale_object_to_desired_height(obj_to_scale, desired_height, depsgraph, scene):
    if not obj_to_scale or desired_height <= 0:
        print("Scaling skipped: No object or invalid target height.")
        return

    print(f"Starting scaling for '{obj_to_scale.name}' to target height {desired_height:.3f}.")

    bpy.ops.object.select_all(action='DESELECT')
    def select_hierarchy(obj):
        obj.select_set(True)
        for child in obj.children:
            select_hierarchy(child)

    if obj_to_scale.name in scene.objects:
        select_hierarchy(obj_to_scale)
        if scene.view_layers[0].objects.active != obj_to_scale :
            scene.view_layers[0].objects.active = obj_to_scale

        if bpy.context.selected_objects:
            try:
                print("Applying existing transformations (especially scale) before recalculation...")
                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                bpy.context.view_layer.update()
            except RuntimeError as e:
                print(f"Warning: Could not apply existing scale: {e}")
        else:
            print("Warning: No objects selected for transform_apply.")
            return
    else:
        print(f"Warning: Object '{obj_to_scale.name}' not in scene for scale application.")
        return

    meshes_in_hierarchy = []
    def get_meshes_recursive(obj_node):
        if obj_node and obj_node.name in scene.objects:
            if obj_node.type == 'MESH' and obj_node.data and obj_node.data.vertices:
                meshes_in_hierarchy.append(obj_node)
            for child in obj_node.children:
                get_meshes_recursive(child)

    if obj_to_scale.name in scene.objects:
        get_meshes_recursive(obj_to_scale)

    if not meshes_in_hierarchy:
        print(f"Warning: No mesh objects found in the hierarchy of '{obj_to_scale.name}' for dimension measurement. Scaling aborted.")
        return

    min_bb, max_bb = get_selection_bounding_box_world(meshes_in_hierarchy, depsgraph)

    if min_bb is None:
        print(f"Warning: Could not determine bounding box for '{obj_to_scale.name}'. Scaling aborted.")
        return

    current_height = max_bb.z - min_bb.z
    print(f"Current world height (Z) of '{obj_to_scale.name}' and its mesh hierarchy: {current_height:.4f}")

    if current_height < 1e-5:
        print(f"Warning: Current height of '{obj_to_scale.name}' is minimal ({current_height:.4f}). Scaling might be unreliable or skipped.")
        if desired_height > 1e-4:
            print("Attempting a very large scale as starting height is almost zero.")
            return
        else: return

    scale_factor = desired_height / current_height
    print(f"Required scaling factor for '{obj_to_scale.name}': {scale_factor:.4f}")

    obj_to_scale.scale.x *= scale_factor
    obj_to_scale.scale.y *= scale_factor
    obj_to_scale.scale.z *= scale_factor

    bpy.context.view_layer.update()
    print(f"'{obj_to_scale.name}' temporarily scaled. Final application in 'prepare_model'.")

def get_animation_frame_range(scene, an_armature, user_start_str, user_end_str):
    anim_start, anim_end = scene.frame_start, scene.frame_end
    source = "Scene Default"

    if an_armature and an_armature.animation_data and an_armature.animation_data.action:
        action = an_armature.animation_data.action
        if action.frame_range[1] > action.frame_range[0] + 1e-4:
            action_s = int(math.floor(action.frame_range[0]))
            action_e = int(math.ceil(action.frame_range[1]))
            if action_e > action_s:
                anim_start, anim_end = action_s, action_e
                source = f"Action '{action.name}'"

    user_s_val, user_e_val = None, None
    if user_start_str and user_start_str.strip():
        try: user_s_val = int(user_start_str)
        except ValueError: print(f"Warning: Invalid anim_start_frame value: '{user_start_str}'")
    if user_end_str and user_end_str.strip():
        try: user_e_val = int(user_end_str)
        except ValueError: print(f"Warning: Invalid anim_end_frame value: '{user_end_str}'")

    if user_s_val is not None:
        anim_start = user_s_val
        source += f", User Start-Override ({anim_start})"
    if user_e_val is not None:
        anim_end = user_e_val
        source += f", User End-Override ({anim_end})"

    if anim_end < anim_start:
        print(f"Warning: Effective start frame ({anim_start}) is after end frame ({anim_end}). Rendering only frame {anim_start}.")
        anim_end = anim_start

    scene.frame_start, scene.frame_end = anim_start, anim_end
    scene.frame_set(anim_start)
    print(f"Animation frame range from {source} determined: {anim_start} to {anim_end}.")
    return anim_start, anim_end

def main():
    argv = sys.argv
    if "--" not in argv: argv = []
    else: argv = argv[argv.index("--") + 1:]

    parser = argparse.ArgumentParser(description="Blender script for animated spritesheets via INI.")
    parser.add_argument('--config_path', type=str, required=True, help="Path to the temporary INI configuration file.")

    try: args = parser.parse_args(argv)
    except SystemExit as e:
        print(f"Argparse error or help called. Exit code: {e.code}")
        sys.exit(e.code if isinstance(e.code, int) else 1)

    config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    if not os.path.exists(args.config_path):
        print(f"ERROR: Configuration file not found: {args.config_path}"); sys.exit(1)
    config.read(args.config_path); print(f"Configuration loaded from: {args.config_path}")

    cfg_p = config['Paths']
    cfg_r = config['RenderSettings']
    cfg_a = config['Animation']
    cfg_c = config['Camera']

    desired_model_height_cfg = 0
    if 'ModelProcessing' in config:
        cfg_mp = config['ModelProcessing']
        desired_model_height_cfg = cfg_mp.getfloat('desired_model_height', fallback=0)
    else:
        print("INFO: Section [ModelProcessing] not found in temporary Blender config. No automatic scaling to target height.")

    fbx_path = cfg_p.get('model_fbx')
    mat_obj_path = cfg_p.get('material_ref_obj', fallback=None)
    mat_fbx_path = cfg_p.get('material_ref_fbx', fallback=None)
    out_dir = cfg_p.get('output_dir')

    if not (fbx_path and out_dir):
        print("ERROR: model_fbx or output_dir path missing in configuration."); sys.exit(1)
    if not os.path.exists(fbx_path):
        print(f"ERROR: Animation FBX file not found: {fbx_path}"); sys.exit(1)

    res_x = cfg_r.getint('resolution_x', fallback=256)
    res_y = cfg_r.getint('resolution_y', fallback=256)
    rot_steps = cfg_r.getint('rotation_steps', fallback=12)
    rot_axis_str = cfg_r.get('rotation_axis', fallback='Z').upper();
    rot_axis = rot_axis_str if rot_axis_str in 'XYZ' else 'Z'

    clear_scene()
    current_scene = bpy.context.scene
    current_depsgraph = bpy.context.evaluated_depsgraph_get()

    print(f"Importing main FBX: {fbx_path}")
    all_imported_objs, main_armature, main_mesh = import_fbx(fbx_path)
    if not all_imported_objs:
        print(f"ERROR: Main FBX import ({fbx_path}) failed or no objects imported."); sys.exit(1)

    root_model_object = main_armature if main_armature else get_hierarchy_root(all_imported_objs)
    if not root_model_object:
        root_model_object = main_mesh if main_mesh else all_imported_objs[0] if all_imported_objs else None
    if not root_model_object:
        print(f"ERROR: Could not determine root object from main FBX ({fbx_path})."); sys.exit(1)
    print(f"Root object for processing identified: '{root_model_object.name}' (Type: {root_model_object.type})")

    if not main_mesh and root_model_object.type == 'MESH':
        main_mesh = root_model_object
    elif not main_mesh and main_armature:
        for child in main_armature.children:
            if child.type == 'MESH': main_mesh = child; break
    print(f"Primary mesh for material assignment: '{main_mesh.name if main_mesh else 'No explicit mesh found'}'")

    if desired_model_height_cfg > 0:
        scale_object_to_desired_height(root_model_object, desired_model_height_cfg, current_depsgraph, current_scene)
        current_depsgraph.update()
    else:
        print("INFO: No explicit target height ('desired_model_height' <= 0 or not configured) specified.")
        bpy.ops.object.select_all(action='DESELECT')
        selected_for_initial_apply = []
        def _select_hierarchy_for_initial_apply(obj_node, scene_ref, collection_ref):
            if obj_node and obj_node.name in scene_ref.objects:
                obj_node.select_set(True)
                collection_ref.append(obj_node)
                for child in obj_node.children:
                    _select_hierarchy_for_initial_apply(child, scene_ref, collection_ref)

        if root_model_object and root_model_object.name in current_scene.objects:
            _select_hierarchy_for_initial_apply(root_model_object, current_scene, selected_for_initial_apply)
            if current_scene.view_layers[0].objects.active != root_model_object:
                try: current_scene.view_layers[0].objects.active = root_model_object
                except: pass

            if bpy.context.selected_objects:
                try:
                    print("INFO: Applying existing transformations (esp. scale) of imported model (as no target height set)...")
                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                    current_depsgraph.update()
                    print("INFO: Existing scale applied.")
                except RuntimeError as e:
                    print(f"WARNING during initial transform_apply (no target height): {e}")
        elif root_model_object:
            print(f"WARNING: Root object '{root_model_object.name}' not in scene for initial transform_apply.")

    loaded_src_materials = {}
    temp_mat_import_objs = []
    mat_source_loaded = False

    if mat_fbx_path and os.path.exists(mat_fbx_path):
        print(f"Attempting material FBX: {mat_fbx_path}")
        try:
            mats, temp_objs = import_fbx_for_materials(mat_fbx_path)
            if mats: loaded_src_materials.update(mats); temp_mat_import_objs.extend(temp_objs); mat_source_loaded = True
            else: print(f"Warning: No materials loaded from material FBX '{mat_fbx_path}'.")
        except Exception as e_mat_fbx: print(f"ERROR loading material FBX: {e_mat_fbx}"); traceback.print_exc()

    if not mat_source_loaded and mat_obj_path and os.path.exists(mat_obj_path):
        print(f"Attempting material OBJ (fallback): {mat_obj_path}")
        try:
            mats, temp_objs = import_obj_for_materials(mat_obj_path)
            if mats: loaded_src_materials.update(mats); temp_mat_import_objs.extend(temp_objs); mat_source_loaded = True
            else: print(f"Warning: No materials loaded from material OBJ '{mat_obj_path}'.")
        except Exception as e_mat_obj: print(f"ERROR loading material OBJ: {e_mat_obj}"); traceback.print_exc()

    if not mat_source_loaded:
        if (mat_fbx_path and not os.path.exists(mat_fbx_path)) or \
           (mat_obj_path and not os.path.exists(mat_obj_path)):
            print("Warning: Specified material reference file not found.")
        elif not mat_fbx_path and not mat_obj_path: print("Info: No material reference file specified.")

    if main_mesh and loaded_src_materials:
        transfer_materials(main_mesh, loaded_src_materials)
    elif main_mesh and not loaded_src_materials and (mat_fbx_path or mat_obj_path):
        print("Warning: Material reference specified, but no materials loaded. Original materials will remain (if any).")
    elif not main_mesh and loaded_src_materials:
        print("Warning: Materials were loaded, but no primary mesh identified for material transfer.")
    elif not main_mesh and not loaded_src_materials:
        print("Info: No primary mesh identified and no external materials loaded.")

    for temp_obj in temp_mat_import_objs:
        if temp_obj and temp_obj.name in bpy.data.objects:
            bpy.data.objects.remove(temp_obj, do_unlink=True)
    if loaded_src_materials and main_mesh and main_mesh.material_slots:
        main_mesh_mats = {slot.material for slot in main_mesh.material_slots if slot.material}
        for mat_name_iter, mat_data_iter in list(loaded_src_materials.items()):
            if mat_data_iter not in main_mesh_mats and mat_data_iter.users == 0:
                try: bpy.data.materials.remove(mat_data_iter)
                except: pass
    print("Material processing and cleanup completed.")

    if root_model_object:
        prepare_model(root_model_object, current_scene)
        current_depsgraph.update()
    else:
        print("ERROR: No root model object present for prepare_model. Aborting."); sys.exit(1)

    cam, cam_target = setup_camera_and_lighting(cfg_c, res_x, res_y, root_model_object)

    current_scene.render.engine = 'BLENDER_EEVEE'
    current_scene.render.resolution_x, current_scene.render.resolution_y = res_x, res_y
    current_scene.render.image_settings.file_format = 'PNG'
    film_trans = cfg_r.getboolean('film_transparent', fallback=True)
    debug_no_trans_bg = cfg_r.getboolean('debug_no_transparent_background', fallback=False)

    if debug_no_trans_bg:
        current_scene.render.film_transparent = False
        current_scene.render.image_settings.color_mode = 'RGB'
        print("INFO: Debug mode: Background will NOT be rendered transparently.")
    else:
        current_scene.render.film_transparent = film_trans
        current_scene.render.image_settings.color_mode = 'RGBA' if film_trans else 'RGB'

    current_scene.eevee.taa_render_samples = cfg_r.getint('eevee_taa_render_samples', fallback=16)
    current_scene.view_settings.view_transform = 'Standard'

    if not os.path.exists(out_dir): os.makedirs(out_dir)
    print(f"Output directory for frames: {out_dir}")

    anim_f_start, anim_f_end = get_animation_frame_range(current_scene, main_armature,
                                                         cfg_a.get('anim_start_frame', fallback=None),
                                                         cfg_a.get('anim_end_frame', fallback=None))
    num_anim_frames = anim_f_end - anim_f_start + 1

    print(f"Rendering {num_anim_frames} animation poses (frames {anim_f_start} to {anim_f_end}) for {rot_steps} angles.")

    obj_to_rotate_around_world_origin = root_model_object
    initial_obj_rotation_euler = obj_to_rotate_around_world_origin.rotation_euler.copy() if obj_to_rotate_around_world_origin else mathutils.Euler((0,0,0), 'XYZ')
    total_rendered_count = 0
    verbose_render_loop = cfg_r.getboolean('verbose_render_loop', fallback=False)

    for angle_step_idx in range(rot_steps):
        rotation_angle_rad = angle_step_idx * (2 * math.pi / rot_steps)

        current_angle_base_rotation_euler = initial_obj_rotation_euler.copy()
        if rot_axis == 'X': current_angle_base_rotation_euler.x += rotation_angle_rad
        elif rot_axis == 'Y': current_angle_base_rotation_euler.y += rotation_angle_rad
        elif rot_axis == 'Z': current_angle_base_rotation_euler.z += rotation_angle_rad

        if obj_to_rotate_around_world_origin:
            obj_to_rotate_around_world_origin.rotation_euler = current_angle_base_rotation_euler
        current_depsgraph.update()

        if verbose_render_loop or (angle_step_idx % (max(1, rot_steps // 4)) == 0) or angle_step_idx == rot_steps -1:
            print(f"Processing angle: {angle_step_idx+1}/{rot_steps}")

        for anim_pose_idx in range(num_anim_frames):
            current_anim_frame = anim_f_start + anim_pose_idx
            current_scene.frame_set(current_anim_frame)
            current_depsgraph.update()

            output_png_filename = f"angle_{angle_step_idx:03d}_animframe_{anim_pose_idx:04d}.png"
            current_scene.render.filepath = os.path.join(out_dir, output_png_filename)

            if verbose_render_loop and (anim_pose_idx % (max(1, num_anim_frames // 2)) == 0 or anim_pose_idx == num_anim_frames-1):
                print(f"  Rendering angle {angle_step_idx:03d}, pose {anim_pose_idx:04d} -> {output_png_filename}")

            try:
                bpy.ops.render.render(write_still=True)
                total_rendered_count += 1
            except RuntimeError as render_err:
                print(f"ERROR rendering frame {output_png_filename}: {render_err}")

    if obj_to_rotate_around_world_origin:
        obj_to_rotate_around_world_origin.rotation_euler = initial_obj_rotation_euler
    print(f"--- Rendering completed --- Total {total_rendered_count} frames rendered.")

if __name__ == "__main__":
    final_exit_code = 0
    try:
        print(f"Blender Version: {bpy.app.version_string}")
        main()
    except SystemExit as sys_e:
        final_exit_code = sys_e.code if isinstance(sys_e.code, int) else 1
        print(f"Blender script finished normally (SystemExit with code {final_exit_code})." if final_exit_code == 0 else f"Blender script finished with code {final_exit_code} (SystemExit).")
    except RuntimeError as rt_e:
        print(f"UNHANDLED RUNTIME ERROR in Blender script execution: {rt_e}")
        traceback.print_exc(); final_exit_code = 2
    except Exception as e:
        print(f"UNHANDLED CRITICAL ERROR in Blender script execution: {e}")
        traceback.print_exc(); final_exit_code = 3
    finally:
        print(f"Blender script (render_animated_spritesheet.py) is exiting with final code: {final_exit_code}")
        sys.exit(final_exit_code)