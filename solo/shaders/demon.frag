#version 300 es
// oma-solorpg: a Demon. The colour drains from the screen, blood closes in from the edges
// and the picture tears at its colours, then it passes. The level is baked in by solo desk,
// 1 at the peak and falling to 0.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

const float level = {{level}};
const vec3 blood = vec3(0.62, 0.04, 0.05);

void main() {
    vec2 size = vec2(textureSize(tex, 0));
    vec2 from = v_texcoord - 0.5;
    float r = length(from * vec2(size.x / size.y, 1.0));
    // Red and blue pull apart, more at the edges than in the middle.
    vec2 split = from * 0.014 * level * (0.25 + r);
    vec4 middle = texture(tex, v_texcoord);
    vec3 pixel = vec3(texture(tex, clamp(v_texcoord + split, 0.0, 1.0)).r, middle.g,
                      texture(tex, clamp(v_texcoord - split, 0.0, 1.0)).b);
    float grey = dot(pixel, vec3(0.299, 0.587, 0.114));
    vec3 drained = mix(pixel, vec3(grey) * vec3(1.1, 0.85, 0.85), 0.6 * level);
    float edge = smoothstep(0.25, 1.0, r);
    vec3 outside = drained * 0.3 + blood * 0.7;
    fragColor = vec4(mix(drained, outside, edge * level * 0.9), middle.a);
}
