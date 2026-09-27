#version 300 es
// oma-solorpg: the hero is dead. The screen goes grey and cold, darkening at the edges,
// like an old photograph, and after a while the colour comes back. The level is baked in by
// solo desk: it rises to 1, holds, and falls back to 0.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

const float level = {{level}};

void main() {
    vec4 pixel = texture(tex, v_texcoord);
    vec2 size = vec2(textureSize(tex, 0));
    float r = length((v_texcoord - 0.5) * vec2(size.x / size.y, 1.0));
    float grey = dot(pixel.rgb, vec3(0.299, 0.587, 0.114));
    vec3 ash = vec3(grey) * vec3(0.94, 0.97, 1.02);
    vec3 faded = mix(pixel.rgb, ash, level);
    // Less contrast, as if the life had gone out of the picture too.
    faded = mix(faded, faded * 0.8 + 0.05, level * 0.6);
    faded *= 1.0 - smoothstep(0.2, 1.1, r) * 0.7 * level;
    fragColor = vec4(faded, pixel.a);
}
