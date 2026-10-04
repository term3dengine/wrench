"""
Wrench - Term3D Map Maker
Interactive terminal-based map editor for creating .tmc map files.
"""

import term3d
import math
import time
import os
import sys
import struct
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_DIR = os.path.join(BASE_DIR, 'wrenchtmod', 'maps')


def ensure_maps_dir():
    os.makedirs(MAPS_DIR, exist_ok=True)


def save_tmc(filepath, data):
    """Save map data to .tmc binary format."""
    with open(filepath, 'wb') as f:
        f.write(b'TMC1')

        name_bytes = data['name'].encode('utf-8')
        f.write(struct.pack('<I', len(name_bytes)))
        f.write(name_bytes)
        f.write(struct.pack('<fff', *data['player_start']))
        f.write(struct.pack('<ff', *data['ground']))

        f.write(struct.pack('<I', len(data['objects'])))
        for obj in data['objects']:
            type_bytes = obj['type'].encode('utf-8')
            f.write(struct.pack('<I', len(type_bytes)))
            f.write(type_bytes)
            f.write(struct.pack('<fff', obj['x'], obj['y'], obj['z']))
            f.write(struct.pack('<f', obj['size']))
            f.write(struct.pack('<BBB', *obj['color']))
            f.write(struct.pack('<B', 1 if obj.get('solid', True) else 0))
            f.write(struct.pack('<B', 1 if obj.get('physics', True) else 0))

        f.write(struct.pack('<I', len(data['mods'])))
        for mod in data['mods']:
            mod_bytes = mod['name'].encode('utf-8')
            f.write(struct.pack('<I', len(mod_bytes)))
            f.write(mod_bytes)
            f.write(struct.pack('<I', 0))


def new_map():
    """Create a new empty map."""
    return {
        'name': 'Untitled',
        'player_start': (0.0, 1.7, 0.0),
        'ground': (40.0, 40.0),
        'objects': [],
        'mods': []
    }


def create_ground(width, depth, material):
    hw = width / 2.0
    hd = depth / 2.0
    verts = [
        term3d.Vec3(-hw, 0, hd),
        term3d.Vec3(hw, 0, hd),
        term3d.Vec3(hw, 0, -hd),
        term3d.Vec3(-hw, 0, -hd),
    ]
    faces = [[0, 1, 2, 3]]
    mesh = term3d.Mesh(name='ground', vertices=verts, faces=faces, material=material)
    model = term3d.Model(name='ground', meshes=[mesh])
    return model


def add_cube(map_data, x, y, z, size=1.0):
    """Add a cube object to the map."""
    map_data['objects'].append({
        'type': 'cube',
        'x': x,
        'y': y,
        'z': z,
        'size': size,
        'color': (128, 128, 128),
        'solid': True,
        'physics': True
    })


def draw_map_maker(engine, map_data, selected_obj, mode, cursor_pos, message):
    """Draw the map maker interface."""
    engine.clear_gui()
    w, h = engine.width, engine.height

    engine.draw_text(2, 1, f"Wrench - {map_data['name']}", fg=term3d.Color(255, 255, 0), bg=term3d.Color(0, 0, 0))
    engine.draw_text(1, 2, '=' * (w - 2), fg=term3d.Color(255, 255, 255), bg=term3d.Color(0, 0, 0))

    engine.draw_text(2, 4, f"Mode: {mode}", fg=term3d.Color(0, 255, 255), bg=term3d.Color(0, 0, 0))
    engine.draw_text(2, 5, f"Objects: {len(map_data['objects'])}", fg=term3d.Color(255, 255, 255), bg=term3d.Color(0, 0, 0))
    engine.draw_text(2, 6, f"Ground: {map_data['ground'][0]:.1f} x {map_data['ground'][1]:.1f}", fg=term3d.Color(200, 200, 200), bg=term3d.Color(0, 0, 0))

    start_y = 8
    engine.draw_text(2, start_y, "Objects:", fg=term3d.Color(255, 255, 255), bg=term3d.Color(0, 0, 0))
    
    for i, obj in enumerate(map_data['objects']):
        y = start_y + 1 + i
        if y >= h - 5:
            break
        marker = ">" if i == selected_obj else " "
        color = term3d.Color(255, 255, 255) if i != selected_obj else term3d.Color(255, 255, 0)
        engine.draw_text(2, y, f"{marker} [{obj['type']}] ({obj['x']:.1f}, {obj['y']:.1f}, {obj['z']:.1f}) size={obj['size']:.1f}", 
                        fg=color, bg=term3d.Color(0, 0, 0))

    if not map_data['objects']:
        engine.draw_text(2, start_y + 1, "(no objects yet)", fg=term3d.Color(150, 150, 150), bg=term3d.Color(0, 0, 0))

    help_y = h - 5
    engine.draw_text(1, help_y - 1, '=' * (w - 2), fg=term3d.Color(255, 255, 255), bg=term3d.Color(0, 0, 0))
    engine.draw_text(2, help_y, "W/S=Navigate objects  N=New object  D=Delete  E=Edit  S=Save  ESC=Back", 
                    fg=term3d.Color(200, 200, 200), bg=term3d.Color(0, 0, 0))

    if message:
        engine.draw_text(2, help_y - 2, message, fg=term3d.Color(255, 100, 100), bg=term3d.Color(0, 0, 0))


def run_map_maker():
    """Run the map maker application."""
    ensure_maps_dir()
    
    engine = term3d.Engine()
    engine._setup_terminal()
    
    map_data = new_map()
    selected_obj = -1
    mode = "View"
    cursor_pos = [0.0, 1.0, 0.0]
    message = ""
    message_timer = 0.0
    running = True
    needs_redraw = True

    engine.renderer.camera.position = term3d.Vec3(0, 15, 15)
    engine.renderer.camera.target = term3d.Vec3(0, 0, 0)
    engine.renderer.camera.view = term3d.mat4_look_at(engine.renderer.camera.position, engine.renderer.camera.target, term3d.Vec3(0, 1, 0))
    engine.renderer.camera.view_proj = term3d.mat4_mul(engine.renderer.camera.proj, engine.renderer.camera.view)

    def on_key(ch):
        nonlocal selected_obj, mode, running, message, message_timer, cursor_pos, needs_redraw
        
        if ch == '\x1b':
            if mode == "Edit":
                mode = "View"
                message = ""
            else:
                running = False
                return
        elif ch == '\r' or ch == '\n':
            if mode == "Edit" and selected_obj >= 0:
                pass
            elif mode == "NewObject":
                add_cube(map_data, cursor_pos[0], cursor_pos[1], cursor_pos[2])
                selected_obj = len(map_data['objects']) - 1
                mode = "View"
                message = f"Added cube at ({cursor_pos[0]:.1f}, {cursor_pos[1]:.1f}, {cursor_pos[2]:.1f})"
                message_timer = 2.0
        elif ch.lower() == 'n':
            if mode == "View":
                mode = "NewObject"
                cursor_pos = [0.0, 1.0, 0.0]
                message = "Enter position (W/S/X=move XYZ, Enter=place, ESC=cancel)"
                message_timer = 5.0
        elif ch.lower() == 'd':
            if mode == "View" and selected_obj >= 0:
                obj = map_data['objects'][selected_obj]
                map_data['objects'].pop(selected_obj)
                selected_obj = min(selected_obj, len(map_data['objects']) - 1)
                message = f"Deleted {obj['type']}"
                message_timer = 2.0
        elif ch.lower() == 'e':
            if mode == "View" and selected_obj >= 0:
                mode = "Edit"
                obj = map_data['objects'][selected_obj]
                message = f"Editing: {obj['type']} at ({obj['x']:.1f}, {obj['y']:.1f}, {obj['z']:.1f}) - W/S=Y +/- 0.5, A/D=X +/- 0.5, Q/E=Z +/- 0.5, ESC=done"
                message_timer = 5.0
        elif ch.lower() == 's':
            if mode == "View":
                ensure_maps_dir()
                filename = map_data['name'].replace(' ', '_').lower() + '.tmc'
                filepath = os.path.join(MAPS_DIR, filename)
                save_tmc(filepath, map_data)
                message = f"Saved to {filename}"
                message_timer = 3.0
        elif ch.lower() == 'w':
            if mode == "View":
                selected_obj = max(0, selected_obj - 1)
            elif mode == "Edit" and selected_obj >= 0:
                map_data['objects'][selected_obj]['y'] += 0.5
            elif mode == "NewObject":
                cursor_pos[1] += 0.5
        elif ch.lower() == 's':
            if mode == "View":
                selected_obj = min(len(map_data['objects']) - 1, selected_obj + 1)
            elif mode == "Edit" and selected_obj >= 0:
                map_data['objects'][selected_obj]['y'] -= 0.5
            elif mode == "NewObject":
                cursor_pos[1] -= 0.5
        elif ch.lower() == 'a':
            if mode == "Edit" and selected_obj >= 0:
                map_data['objects'][selected_obj]['x'] -= 0.5
            elif mode == "NewObject":
                cursor_pos[0] -= 0.5
        elif ch.lower() == 'd':
            if mode == "Edit" and selected_obj >= 0:
                map_data['objects'][selected_obj]['x'] += 0.5
            elif mode == "NewObject":
                cursor_pos[0] += 0.5
        elif ch.lower() == 'q':
            if mode == "Edit" and selected_obj >= 0:
                map_data['objects'][selected_obj]['z'] -= 0.5
            elif mode == "NewObject":
                cursor_pos[2] -= 0.5
        elif ch.lower() == 'e':
            if mode == "Edit" and selected_obj >= 0:
                map_data['objects'][selected_obj]['z'] += 0.5
            elif mode == "NewObject":
                cursor_pos[2] += 0.5
        
        needs_redraw = True

    engine.on_key_down = on_key

    def update(dt):
        nonlocal needs_redraw, message_timer, message
        
        if message_timer > 0:
            message_timer -= dt
            if message_timer <= 0:
                message = ""
                needs_redraw = True

        if not needs_redraw:
            return

        needs_redraw = False
        models = []
        ground = create_ground(map_data['ground'][0], map_data['ground'][1],
                              material=term3d.Material(name='ground', color=term3d.Color(60, 100, 60)))
        ground.position = term3d.Vec3(0, 0, 0)
        models.append(ground)

        for obj in map_data['objects']:
            mat = term3d.Material(name=obj['type'], color=term3d.Color(*obj['color']))
            model = term3d.create_cube(obj['size'], material=mat)
            model.position = term3d.Vec3(obj['x'], obj['y'], obj['z'])
            models.append(model)

        if mode == "NewObject":
            cursor_mat = term3d.Material(name='cursor', color=term3d.Color(255, 255, 0))
            cursor_model = term3d.create_cube(0.5, material=cursor_mat)
            cursor_model.position = term3d.Vec3(cursor_pos[0], cursor_pos[1], cursor_pos[2])
            models.append(cursor_model)

        engine.clear_models()
        for m in models:
            engine.add_model(m)

        draw_map_maker(engine, map_data, selected_obj, mode, cursor_pos, message)

    engine.run(update_func=update)
    engine._restore_terminal()


def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    
    selected = 0
    options = ["New Map", "Load Map", "Exit"]

    def draw_main_menu():
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 60)
        print("Wrench - Term3D Map Maker")
        print("=" * 60)
        print()
        print("Options:")
        for i, item in enumerate(options):
            if i == selected:
                print(f"  > {item}")
            else:
                print(f"    {item}")
        print()
        print("W/S=Select Enter=Confirm ESC=Exit")
        print()

    draw_main_menu()

    while True:
        try:
            import msvcrt
            ch = msvcrt.getch()
            if ch == b'\x1b':
                return
            elif ch == b'\x00' or ch == b'\xe0':
                ch2 = msvcrt.getch()
                if ch2 == b'H':
                    selected = (selected - 1) % len(options)
                elif ch2 == b'P':
                    selected = (selected + 1) % len(options)
            elif ch == b'\r':
                if selected == 0:
                    print("\nStarting new map...")
                    run_map_maker()
                    draw_main_menu()
                elif selected == 1:
                    maps = []
                    ensure_maps_dir()
                    for f in sorted(os.listdir(MAPS_DIR)):
                        if f.endswith('.tmc'):
                            maps.append(f)
                    if not maps:
                        print("\nNo maps found.")
                        input("Press Enter...")
                    else:
                        print("\nAvailable maps:")
                        for i, m in enumerate(maps):
                            print(f"  {i + 1}. {m}")
                        print("  0. Back")
                        try:
                            choice = int(input("\nSelect map number: ").strip())
                            if choice == 0:
                                pass
                            elif 1 <= choice <= len(maps):
                                print(f"\nLoading map: {maps[choice - 1]}...")
                                print("(Map loading in Wrench not yet implemented)")
                                input("Press Enter...")
                        except ValueError:
                            pass
                elif selected == 2:
                    return
            elif ch.lower() == b'w':
                selected = (selected - 1) % len(options)
            elif ch.lower() == b's':
                selected = (selected + 1) % len(options)
            draw_main_menu()
        except ImportError:
            choice = input("Choice: ").strip().lower()
            if choice == '1':
                run_map_maker()
            elif choice == '2':
                print("(Map loading not yet implemented)")
                input("Press Enter...")
            elif choice == '3':
                return
            draw_main_menu()


if __name__ == '__main__':
    main()
