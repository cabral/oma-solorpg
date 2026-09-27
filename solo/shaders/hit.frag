#version 300 es
// oma-solorpg: the hero takes a blow. The screen jolts sideways and flushes red at the
// edges, then settles. The level is baked in by solo desk, 1 at the blow and falling to 0.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

const float level = {{level}};

void main() {
    vec2 size = vec2(textureSize(tex, 0));
    // The jolt swings back and forth as it dies away.
    vec2 uv = v_texcoord + vec2(sin(level * 23.0) * 0.006 * level, 0.0);
    vec4 pixel = texture(tex, clamp(uv, 0.0, 1.0));
    float r = length((v_texcoord - 0.5) * vec2(size.x / size.y, 1.0));
    float edge = smoothstep(0.35, 1.0, r);
    vec3 hurt = mix(pixel.rgb, vec3(0.72, 0.04, 0.04), edge * level * 0.75);
    hurt += vec3(0.1, 0.0, 0.0) * level * (1.0 - edge);
    fragColor = vec4(clamp(hurt, 0.0, 1.0), pixel.a);
}
