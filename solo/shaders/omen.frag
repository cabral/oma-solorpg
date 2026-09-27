#version 300 es
// oma-solorpg: an omen. Something stirs: the screen ripples like water, the colour turns
// cold and green, and the edges darken, then it passes. The level is baked in by solo desk
// (it rises, holds and falls), and so is the phase that moves the ripple, a step at a
// time (Hyprland's time uniform would need damage tracking switched off).
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

const float level = {{level}};
const float phase = {{phase}};

void main() {
    vec2 uv = v_texcoord;
    uv.x += sin(uv.y * 34.0 + phase * 2.4) * 0.0022 * level;
    uv.y += sin(uv.x * 21.0 - phase * 1.7) * 0.0014 * level;
    vec4 pixel = texture(tex, clamp(uv, 0.0, 1.0));
    vec2 size = vec2(textureSize(tex, 0));
    float r = length((v_texcoord - 0.5) * vec2(size.x / size.y, 1.0));
    float grey = dot(pixel.rgb, vec3(0.299, 0.587, 0.114));
    vec3 cold = mix(pixel.rgb, vec3(grey) * vec3(0.72, 0.98, 0.9), 0.55 * level);
    float edge = smoothstep(0.3, 1.05, r);
    cold = mix(cold, cold * 0.35 + vec3(0.02, 0.09, 0.08), edge * level * 0.8);
    fragColor = vec4(cold, pixel.a);
}
