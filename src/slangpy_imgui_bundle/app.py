from pathlib import Path
from typing import List, Sequence
from imgui_bundle import imgui
import slangpy as spy
from pyglm import glm

import slangpy_imgui_bundle
from slangpy_imgui_bundle.imgui_adapter import ImguiAdapter


class App:
    # Window config.
    window_size = glm.ivec2(960, 540)
    window_title = "SlangPy Application"
    window_resizable = True

    # SGL config.
    device_type = spy.DeviceType.automatic
    enable_debug_layer = False
    shader_paths = [slangpy_imgui_bundle.GUI_SHADER_PATH]

    def __init__(self, user_shader_paths: List[Path] = []) -> None:
        self.window = spy.Window(
            width=self.window_size.x,
            height=self.window_size.y,
            title=self.window_title,
            resizable=self.window_resizable,
        )
        # Append user shader paths to default shader paths.
        self.shader_paths.extend(user_shader_paths)
        # Create SGL device.
        self.device = spy.create_device(
            type=self.device_type,
            enable_debug_layers=self.enable_debug_layer,
            include_paths=self.shader_paths,
        )

        # Setup renderer.
        imgui.create_context()
        self.adapter = ImguiAdapter(self.window, self.device)

        self.window.on_resize = self.on_resize
        self.window.on_mouse_event = self.on_mouse_event
        self.window.on_keyboard_event = self.on_keyboard_event
        self.window.on_drop_files = self.on_drop_files
        self.window.on_gamepad_event = self.on_gamepad_event
        self.window.on_gamepad_state = self.on_gamepad_state

    def on_resize(self, width: int, height: int) -> None:
        self.adapter.resize(width, height)

    def on_mouse_event(self, event: spy.MouseEvent) -> None:
        self.adapter.mouse_event(event)

    def on_keyboard_event(self, event: spy.KeyboardEvent) -> None:
        self.adapter.key_event(event)
        self.adapter.unicode_input(event.codepoint)

    def on_gamepad_event(self, event: spy.GamepadEvent) -> None:
        pass

    def on_gamepad_state(self, state: spy.GamepadState) -> None:
        pass

    def on_drop_files(self, file_paths: Sequence[str]) -> None:
        pass

    def run(self) -> None:
        while not self.window.should_close():
            # Poll events.
            self.window.process_events()
            # Start ImGui frame.
            imgui.new_frame()

            # Your application code here.
            imgui.begin("Hello, SlangPy ImGui Bundle!")
            imgui.text("This is a sample application using SlangPy ImGui Bundle.")
            imgui.end()

            imgui.render()
            # Render ImGui.
            self.adapter.render(imgui.get_draw_data())
