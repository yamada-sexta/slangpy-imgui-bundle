"""
Slangpy adapter for ImGui Bundle
"""

from abc import ABC
import ctypes
import logging
import slangpy as spy
from imgui_bundle import ImVec2, imgui


logger = logging.getLogger(__name__)


REVERSE_KEY_MAP = {
    spy.KeyCode.tab: imgui.Key.tab,
    spy.KeyCode.left: imgui.Key.left_arrow,
    spy.KeyCode.right: imgui.Key.right_arrow,
    spy.KeyCode.up: imgui.Key.up_arrow,
    spy.KeyCode.down: imgui.Key.down_arrow,
    spy.KeyCode.page_up: imgui.Key.page_up,
    spy.KeyCode.page_down: imgui.Key.page_down,
    spy.KeyCode.home: imgui.Key.home,
    spy.KeyCode.end: imgui.Key.end,
    spy.KeyCode.delete: imgui.Key.delete,
    spy.KeyCode.space: imgui.Key.space,
    spy.KeyCode.backspace: imgui.Key.backspace,
    spy.KeyCode.enter: imgui.Key.enter,
    spy.KeyCode.escape: imgui.Key.escape,
}


class ImguiAdapter:
    """
    The slangpy renderer adapter for ImGui Bundle.
    """

    def __init__(self, window: spy.Window, device: spy.Device) -> None:
        # Registered textures.
        self._textures = {}

        self.window = window
        self.device = device

        # Create window surface.
        self.surface = self.device.create_surface(self.window)
        self.surface.configure(width=self.window.width, height=self.window.height)

        # Initialize render pipeline resources.
        self.frame_buffer = self._create_frame_buffer(
            self.window.width, self.window.height
        )

        # Input layout.
        self.input_layout = self.device.create_input_layout(
            input_elements=[
                {
                    "semantic_name": "POSITION",
                    "semantic_index": 0,
                    "format": spy.Format.rg32_float,
                },
                {
                    "semantic_name": "TEXCOORD",
                    "semantic_index": 0,
                    "format": spy.Format.rg32_float,
                },
                {
                    "semantic_name": "COLOR",
                    "semantic_index": 0,
                    "format": spy.Format.rgba8_unorm,
                },
            ],
            vertex_streams=[{"stride": 20}],
        )
        # Load shader modules.
        self.program = self.device.load_program(
            "imgui_renderer.slang", ["vertexMain", "fragmentMain"]
        )
        self.pipeline = self.device.create_render_pipeline(
            program=self.program,
            input_layout=self.input_layout,
            targets=[
                {
                    "format": spy.Format.rgba16_float,
                }
            ],
        )

        # Get ImGui IO.
        self.io = imgui.get_io()
        # Font texture.
        self._font_texture = None
        self.refresh_font_texture()

        # Resize ImGui display size.
        self.resize(self.window.width, self.window.height)

    def register_texture(self, texture: spy.Texture) -> None:
        texture_id = texture.native_handle.value
        self._textures[texture_id] = texture

    def unregister_texture(self, texture: spy.Texture) -> None:
        texture_id = texture.native_handle.value
        if texture_id in self._textures:
            del self._textures[texture_id]

    def render(self, draw_data: imgui.ImDrawData) -> None:
        """Method to render ImGui draw data at the end of each frame.

        :param draw_data: The ImGui draw data to render.
        """
        # Acquire next surface texture.
        surface_texture = self.surface.acquire_next_image()

        # Rendering commands.
        command_encoder = self.device.create_command_encoder()

        # Projection matrix.
        width, height = self.io.display_size.x, self.io.display_size.y
        fb_w = int(width * self.io.display_framebuffer_scale.x)
        fb_h = int(height * self.io.display_framebuffer_scale.y)
        proj_matrix = [
            [2.0 / width, 0.0, 0.0, 0.0],
            [0.0, -2.0 / height, 0.0, 0.0],
            [0.0, 0.0, -1.0, 0.0],
            [-1.0, 1.0, 0.0, 1.0],
        ]

        for commands in draw_data.cmd_lists:
            vtx_type = ctypes.c_byte * commands.vtx_buffer.size() * imgui.VERTEX_SIZE
            idx_type = ctypes.c_uint32 * commands.idx_buffer.size() * imgui.INDEX_SIZE
            vtx_arr = (vtx_type).from_address(commands.vtx_buffer.data_address())
            idx_arr = (idx_type).from_address(commands.idx_buffer.data_address())
            # Update vertex buffer.
            vertex_buffer = self.device.create_buffer(
                usage=spy.BufferUsage.vertex_buffer | spy.BufferUsage.shader_resource,
                label="imgui_vertex_buffer",
                data=bytes(vtx_arr),
            )
            # Update index buffer.
            index_buffer = self.device.create_buffer(
                usage=spy.BufferUsage.index_buffer | spy.BufferUsage.shader_resource,
                label="imgui_index_buffer",
                data=bytes(idx_arr),
            )

            idx_offset = 0
            for command in commands.cmd_buffer:
                texture = self._textures.get(command.get_tex_id())
                if texture is None:
                    raise ValueError("Texture not registered with ImguiAdapter.")

                # Render ImGui draw data to the frame buffer.
                with command_encoder.begin_render_pass(
                    {"color_attachments": [{"view": self.frame_buffer.create_view({})}]}
                ) as pass_encoder:
                    root = pass_encoder.bind_pipeline(self.pipeline)
                    root_cursor = spy.ShaderCursor(root)
                    root_cursor["uniforms"]["proj"].set_data(proj_matrix)
                    root_cursor["uniforms"]["texture"].write(texture)

                    x, y, z, w = (
                        command.clip_rect.x,
                        command.clip_rect.y,
                        command.clip_rect.z,
                        command.clip_rect.w,
                    )

                    pass_encoder.set_render_state(
                        {
                            "viewports": [
                                spy.Viewport.from_size(
                                    self.frame_buffer.width, self.frame_buffer.height
                                )
                            ],
                            "scissor_rects": [
                                spy.ScissorRect(
                                    {
                                        "min_x": int(x),
                                        "min_y": int(y),
                                        "max_x": int(z),
                                        "max_y": int(w),
                                    }
                                )
                            ],
                            "vertex_buffers": [vertex_buffer],
                            "index_buffer": index_buffer,
                            "index_format": spy.IndexFormat.uint32,
                        }
                    )
                    pass_encoder.draw(
                        {
                            "vertex_count": command.elem_count,
                            "start_index_location": idx_offset,
                        }
                    )
                    idx_offset += command.elem_count

        # Blit to the surface texture.
        command_encoder.blit(surface_texture, self.frame_buffer)
        self.device.submit_command_buffer(command_encoder.finish())
        del surface_texture

        self.surface.present()

    def refresh_font_texture(self) -> None:
        """Method to refresh the font texture used by ImGui."""
        texture_data = self.io.fonts.tex_data.get_pixels_array()
        width, height = texture_data.shape

        if self._font_texture is not None:
            self.unregister_texture(self._font_texture)

        self._font_texture = self.device.create_texture(
            format=spy.Format.r8_unorm,
            width=width,
            height=height,
            usage=spy.TextureUsage.shader_resource,
            label="imgui_font_texture",
            data=texture_data.tobytes(),
        )
        self.register_texture(self._font_texture)
        self.io.fonts.tex_data.tex_id = self._font_texture.native_handle.value
        self.io.fonts.clear_tex_data()

    def resize(self, width: int, height: int, fb_scale: float = 1) -> None:
        """Method to handle window resizing.

        :param width: The new width of the window.
        :param height: The new height of the window.
        """
        # Update ImGui display size.
        self.io.display_size = ImVec2(width, height)
        self.io.display_framebuffer_scale = ImVec2(fb_scale, fb_scale)
        # Update framebuffer scale.
        self.device.wait()
        if width > 0 and height > 0:
            self.surface.configure(width, height)
            self.frame_buffer = self._create_frame_buffer(width, height)
        else:
            self.surface.unconfigure()

    def key_event(self, event: spy.KeyboardEvent) -> None:
        """Method to handle keyboard events.

        :param event: The keyboard event.
        """
        key = event.key
        if key in REVERSE_KEY_MAP:
            imgui_key = REVERSE_KEY_MAP[key]
            down = event.is_key_press()
            self.io.add_key_event(imgui_key, down)

    def mouse_event(self, event: spy.MouseEvent) -> None:
        """Method to handle mouse events.

        :param event: The mouse event.
        """
        # Mouse move event.
        if event.is_move():
            self.io.mouse_pos = ImVec2(*event.pos)
        if event.is_button_down() or event.is_button_up():
            down = event.is_button_down()
            if event.button == spy.MouseButton.left:
                self.io.mouse_down[0] = down
            elif event.button == spy.MouseButton.right:
                self.io.mouse_down[1] = down
            elif event.button == spy.MouseButton.middle:
                self.io.mouse_down[2] = down
        if event.is_scroll():
            self.io.mouse_wheel += event.scroll.y
            self.io.mouse_wheel_h += event.scroll.x

    def unicode_input(self, codepoint: int) -> None:
        """Method to handle unicode character input.

        :param codepoint: The unicode codepoint.
        """
        self.io.add_input_character(codepoint)

    def shutdown(self) -> None:
        """Method to shutdown the renderer and release resources."""
        pass

    def _create_frame_buffer(self, width: int, height: int) -> spy.Texture:
        return self.device.create_texture(
            format=spy.Format.rgba16_float,
            width=width,
            height=height,
            usage=spy.TextureUsage.shader_resource | spy.TextureUsage.unordered_access,
            label="output_texture",
        )
