#version 300 es
// oma-solorpg: a Dragon. Gold light floods in from the edges of the screen and warms
// everything it touches, then fades. solo desk bakes the level in (1 at the peak, falling
// to 0) into one file per step, and puts the player's own shader back afterwards.
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

const float level = {{level}};
const vec3 gold = vec3(0.91, 0.73, 0.28);

void main() {
    vec4 pixel = texture(tex, v_texcoord);
    vec2 size = vec2(textureSize(tex, 0));
    float r = length((v_texcoord - 0.5) * vec2(size.x / size.y, 1.0));
    float edge = smoothstep(0.3, 1.05, r);
    // Brights catch the light more than darks, as gilding does.
    float bright = dot(pixel.rgb, vec3(0.299, 0.587, 0.114));
    vec3 lit = pixel.rgb * mix(vec3(1.0), vec3(1.12, 1.02, 0.8), level);
    lit += gold * level * (edge * 0.6 + bright * 0.12);
    fragColor = vec4(clamp(lit, 0.0, 1.0), pixel.a);
}
