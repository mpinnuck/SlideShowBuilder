# slideshow/transitions/origami_render.py
"""
Shared ModernGL rendering functions for origami-style transitions.
Provides Phase 1 (fold) and a single reusable Phase 2 (unfold) function
that works for both left and right horizontal folds.
"""

import numpy as np
import moderngl


# ---------- SHADER CACHE ----------

class ShaderCache:
    """Global shader cache to avoid recompiling shaders across fold operations."""
    _cache = {}
    
    @classmethod
    def get_or_create_program(cls, ctx, key, vertex_shader, fragment_shader):
        """Get cached shader program or create and cache new one."""
        cache_key = (id(ctx), key)
        if cache_key not in cls._cache:
            cls._cache[cache_key] = ctx.program(
                vertex_shader=vertex_shader,
                fragment_shader=fragment_shader
            )
        return cls._cache[cache_key]
    
    @classmethod
    def clear_cache(cls):
        """Clear shader cache - useful for testing or context changes."""
        cls._cache.clear()


# ---------- EASING FUNCTIONS ----------

def ease_in_out_quad(t):
    """
    Quadratic ease-in-out easing function for smooth animation.
    
    Args:
        t: Time parameter between 0.0 and 1.0
        
    Returns:
        Eased value between 0.0 and 1.0
        
    Behavior:
        - Starts slow (ease-in)
        - Accelerates in the middle
        - Ends slow (ease-out)
        - Creates organic, natural motion
    """
    if t < 0.5:
        return 2.0 * t * t
    else:
        return 1.0 - 2.0 * (1.0 - t) * (1.0 - t)

def ease_in_out_cubic(t):
    """
    Cubic ease-in-out easing function for more pronounced smooth animation.
    
    Args:
        t: Time parameter between 0.0 and 1.0
        
    Returns:
        Eased value between 0.0 and 1.0
    """
    if t < 0.5:
        return 4.0 * t * t * t
    else:
        p = 2.0 * t - 2.0
        return 1.0 + p * p * p / 2.0

def ease_out_back(t):
    """
    Back ease-out easing function with slight overshoot for bouncy effect.
    
    Args:
        t: Time parameter between 0.0 and 1.0
        
    Returns:
        Eased value between 0.0 and 1.0 (may slightly exceed 1.0 for overshoot)
    """
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * pow(t - 1.0, 3) + c1 * pow(t - 1.0, 2)



# ---------- MESH GENERATORS ----------

def generate_full_screen_mesh_x(segments=20, x_min=-1.0, x_max=1.0):
    """Generate vertices/indices for a mesh spanning x_min..x_max in NDC (for horizontal folds)."""
    vertices, tex_coords, indices = [], [], []
    x_start = int((x_min + 1) / 2 * segments)
    x_end = int((x_max + 1) / 2 * segments)
    for y in range(segments + 1):
        for x in range(x_start, x_end + 1):
            u = x / segments
            v = y / segments
            vertices.extend([(u - 0.5) * 2.0, (v - 0.5) * 2.0, 0.0])
            tex_coords.extend([u, 1.0 - v])
    row_vertices = x_end - x_start + 1
    for y in range(segments):
        for x in range(row_vertices - 1):
            tl = y * row_vertices + x
            tr = tl + 1
            bl = (y + 1) * row_vertices + x
            br = bl + 1
            indices.extend([tl, bl, tr, tr, bl, br])
    return (np.array(vertices, np.float32),
            np.array(tex_coords, np.float32),
            np.array(indices, np.uint32))

def generate_full_screen_mesh_y(segments=20, y_min=-1.0, y_max=1.0):
    """
    Generate vertices/indices for a mesh spanning y_min..y_max in NDC (for vertical folds).
    This is the vertical equivalent of generate_full_screen_mesh_x (x-based).
    """
    vertices, tex_coords, indices = [], [], []
    y_start = int((y_min + 1) / 2 * segments)
    y_end = int((y_max + 1) / 2 * segments)

    for y in range(y_start, y_end + 1):
        for x in range(segments + 1):
            u = x / segments
            v = y / segments
            vertices.extend([(u - 0.5) * 2.0, (v - 0.5) * 2.0, 0.0])
            tex_coords.extend([u, 1.0 - v])
    row_vertices = segments + 1
    rows = y_end - y_start + 1
    for y in range(rows - 1):
        for x in range(segments):
            tl = y * row_vertices + x
            tr = tl + 1
            bl = (y + 1) * row_vertices + x
            br = bl + 1
            indices.extend([tl, bl, tr, tr, bl, br])
    return (np.array(vertices, np.float32),
            np.array(tex_coords, np.float32),
            np.array(indices, np.uint32))


# ---------- RENDERING UTILITIES ----------

def draw_fullscreen_image(ctx, tex):
    """Draws a full-frame texture to the current framebuffer."""
    prog = ShaderCache.get_or_create_program(
        ctx, 
        "fullscreen_quad",
        vertex_shader="""
        #version 330
        in vec3 in_position;
        in vec2 in_texcoord;
        out vec2 uv;
        void main() {
            uv = in_texcoord;
            gl_Position = vec4(in_position, 1.0);
        }
        """,
        fragment_shader="""
        #version 330
        in vec2 uv;
        out vec4 fragColor;
        uniform sampler2D tex;
        void main() {
            fragColor = texture(tex, uv);
        }
        """
    )

    v = np.array([-1,-1,0,  1,-1,0,  1,1,0, -1,1,0], np.float32)
    uv = np.array([0,1,  1,1,  1,0,  0,0], np.float32)
    idx = np.array([0,1,2, 0,2,3], np.uint32)

    vao = ctx.vertex_array(prog, [
        (ctx.buffer(v.tobytes()), '3f', 'in_position'),
        (ctx.buffer(uv.tobytes()), '2f', 'in_texcoord')
    ], ctx.buffer(idx.tobytes()))

    tex.use(0)
    prog['tex'] = 0
    vao.render()


def render_flap_fold(ctx, from_tex, to_tex, width, height,
                     x_min, x_max, u_min, u_max, seam_x,
                     num_frames, start_angle=0.0, end_angle=np.pi, 
                     previous_frame=None, easing="quad", lighting=True):
    """
    Render one flap folding (e.g. Q4→Q3), revealing TO behind the flap only.
    
    Args:
        ctx: ModernGL context
        from_tex, to_tex: Source and destination textures
        width, height: Frame dimensions
        x_min, x_max, u_min, u_max: Flap geometry and texture coordinates
        seam_x: X-coordinate of the fold seam
        num_frames: Number of animation frames to generate
        start_angle, end_angle: Start and end rotation angles in radians
        previous_frame: Result of previous fold to use as background
        easing: Easing function type ("linear", "quad", "cubic", "back")
        lighting: Enable realistic directional lighting for depth (default: True)
        
    Returns:
        List of rendered frame arrays
    """
    frames = []

    # Lighting parameters for realistic paper-like shading
    light_direction = np.array([-0.3, -0.5, -0.8], dtype=np.float32)  # Top-left-front light
    light_direction = light_direction / np.linalg.norm(light_direction)  # Normalize
    ambient_strength = 0.4  # Base lighting level
    diffuse_strength = 0.8  # Directional light strength

    # Create offscreen framebuffer
    flap_tex = ctx.texture((width, height), 3)
    fbo = ctx.framebuffer(color_attachments=[flap_tex])

    # Prepare flap mesh
    flap_v = np.array([
        x_min, -1, 0,
        x_max, -1, 0,
        x_max,  1, 0,
        x_min,  1, 0
    ], np.float32)
    flap_uv = np.array([
        u_min, 1.0,
        u_max, 1.0,
        u_max, 0.0,
        u_min, 0.0
    ], np.float32)
    flap_idx = np.array([0,1,2,0,2,3], np.uint32)

    # Select shader based on lighting preference
    if lighting:
        flap_prog = ShaderCache.get_or_create_program(
            ctx,
            "flap_fold_lit",
            vertex_shader="""
            #version 330
            in vec3 in_position;
            in vec2 in_texcoord;
            out vec2 uv;
            out vec3 world_pos;
            out vec3 normal;
            uniform float angle;
            uniform float seam_x;
            void main() {
                uv = in_texcoord;
                vec3 pos = in_position;
                float ox = pos.x - seam_x;
                float oz = pos.z;
                
                // Apply fold rotation
                pos.x = seam_x + ox * cos(angle) - oz * sin(angle);
                pos.z = ox * sin(angle) + oz * cos(angle);
                
                // Calculate normal based on fold angle
                // For a fold, the normal rotates with the surface
                vec3 fold_normal = vec3(sin(angle), 0.0, cos(angle));
                // Blend between flat (0,0,1) and folded normal based on distance from seam
                float distance_from_seam = abs(ox);
                normal = normalize(mix(vec3(0.0, 0.0, 1.0), fold_normal, distance_from_seam));
                
                world_pos = pos;
                gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
            }
            """,
            fragment_shader="""
            #version 330
            in vec2 uv;
            in vec3 world_pos;
            in vec3 normal;
            out vec4 fragColor;
            uniform sampler2D tex;
            uniform vec3 light_dir;
            uniform float ambient_strength;
            uniform float diffuse_strength;
            void main() {
                vec3 base_color = texture(tex, uv).rgb;
                
                // Normalize normal (interpolated across triangle)
                vec3 norm = normalize(normal);
                
                // Calculate lighting
                float diff = max(dot(norm, -light_dir), 0.0);
                vec3 ambient = ambient_strength * base_color;
                vec3 diffuse = diffuse_strength * diff * base_color;
                
                // Combine lighting components
                vec3 final_color = ambient + diffuse;
                
                // Add subtle rim lighting for paper-like effect
                float rim = 1.0 - max(dot(norm, vec3(0.0, 0.0, 1.0)), 0.0);
                rim = pow(rim, 2.0) * 0.3;
                final_color += rim * vec3(1.0, 1.0, 1.0);
                
                fragColor = vec4(final_color, 1.0);
            }
            """
        )
    else:
        # Use simple unlit shader for backward compatibility
        flap_prog = ShaderCache.get_or_create_program(
            ctx,
            "flap_fold_simple",
            vertex_shader="""
            #version 330
            in vec3 in_position;
            in vec2 in_texcoord;
            out vec2 uv;
            uniform float angle;
            uniform float seam_x;
            void main() {
                uv = in_texcoord;
                vec3 pos = in_position;
                float ox = pos.x - seam_x;
                float oz = pos.z;
                pos.x = seam_x + ox * cos(angle) - oz * sin(angle);
                pos.z = ox * sin(angle) + oz * cos(angle);
                gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
            }
            """,
            fragment_shader="""
            #version 330
            in vec2 uv;
            out vec4 fragColor;
            uniform sampler2D tex;
            void main() {
                fragColor = texture(tex, uv);
            }
            """
        )

    flap_vao = ctx.vertex_array(flap_prog, [
        (ctx.buffer(flap_v.tobytes()), "3f", "in_position"),
        (ctx.buffer(flap_uv.tobytes()), "2f", "in_texcoord")
    ], ctx.buffer(flap_idx.tobytes()))

    ctx.disable(moderngl.CULL_FACE)

    # Use previous frame as background, or FROM image for first fold
    if previous_frame is not None:
        background_tex = ctx.texture((width, height), 3, previous_frame.tobytes())
    else:
        background_tex = from_tex

    for j in range(num_frames):
        t = j / (num_frames - 1)
        
        # Apply easing function for more organic motion
        if easing == "quad":
            eased_t = ease_in_out_quad(t)
        elif easing == "cubic":
            eased_t = ease_in_out_cubic(t)
        elif easing == "back":
            eased_t = ease_out_back(t)
        else:  # "linear" or any other value
            eased_t = t
            
        angle = start_angle + eased_t * (end_angle - start_angle)

        fbo.use()
        ctx.clear(0, 0, 0, 1)

        # 1️⃣ Draw background (previous fold result or FROM image)
        background_tex.use(0)
        draw_fullscreen_image(ctx, background_tex)

        # 2️⃣ Only reveal TO image in the specific area being folded over
        # Create a quad for just the area being revealed
        reveal_v = np.array([
            x_min, -1, 0,
            x_max, -1, 0, 
            x_max,  1, 0,
            x_min,  1, 0
        ], np.float32)
        reveal_uv = np.array([
            u_min, 1.0,
            u_max, 1.0,
            u_max, 0.0,
            u_min, 0.0
        ], np.float32)
        reveal_idx = np.array([0,1,2,0,2,3], np.uint32)

        # Simple program for revealing TO image
        reveal_prog = ShaderCache.get_or_create_program(
            ctx,
            "reveal_quad",
            vertex_shader="""
            #version 330
            in vec3 in_position;
            in vec2 in_texcoord;
            out vec2 uv;
            void main() {
                uv = in_texcoord;
                gl_Position = vec4(in_position, 1.0);
            }
            """,
            fragment_shader="""
            #version 330
            in vec2 uv;
            out vec4 fragColor;
            uniform sampler2D tex;
            void main() {
                fragColor = texture(tex, uv);
            }
            """
        )

        reveal_vao = ctx.vertex_array(reveal_prog, [
            (ctx.buffer(reveal_v.tobytes()), "3f", "in_position"),
            (ctx.buffer(reveal_uv.tobytes()), "2f", "in_texcoord")
        ], ctx.buffer(reveal_idx.tobytes()))

        # Reveal TO image only in the area being folded over (gradually)
        reveal_progress = min(1.0, angle / (np.pi/2))  # 0 to 1 as angle goes 0 to 90°
        if reveal_progress > 0:
            to_tex.use(0)
            reveal_prog['tex'] = 0
            reveal_vao.render()

        # 3️⃣ Draw FROM flap rotating with lighting
        from_tex.use(0)
        flap_prog['tex'] = 0
        flap_prog['angle'] = angle
        flap_prog['seam_x'] = seam_x
        
        if lighting:
            flap_prog['light_dir'] = tuple(light_direction)
            flap_prog['ambient_strength'] = ambient_strength
            flap_prog['diffuse_strength'] = diffuse_strength
            
        flap_vao.render()

        frame = np.flipud(
            np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
        )
        frames.append(frame.copy())

    return frames