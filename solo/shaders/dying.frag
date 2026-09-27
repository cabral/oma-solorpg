#version 300 es
// oma-solorpg: the hero is dying. The colour has half gone, and a dark red closes in from
// the edges. solo desk bakes in how weak the hero is, 0 at first and toward 1 with each
// failed death roll, and holds this until the hero is saved or dies. It stays still:
// Hyprland's time uniform only moves when something else redraws the screen, so the
// heartbeat is left to the Book. The middle of the screen stays clear enough to read.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

const float weak = {{weak}};

void main() {
    vec4 pixel = texture(tex, v_texcoord);
    vec2 size = vec2(textureSize(tex, 0));
    float r = length((v_texcoord - 0.5) * vec2(size.x / size.y, 1.0));
    float grey = dot(pixel.rgb, vec3(0.299, 0.587, 0.114));
    vec3 drained = mix(pixel.rgb, vec3(grey), 0.4 + 0.2 * weak);
    float closing = smoothstep(0.32 - 0.08 * weak, 1.0, r);
    vec3 dark = drained * 0.2 + vec3(0.35, 0.01, 0.02);
    fragColor = vec4(mix(drained, dark, closing * (0.7 + 0.2 * weak)), pixel.a);
}
