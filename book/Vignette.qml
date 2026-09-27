import QtQuick
import QtQuick.Shapes

// Light and shadow over the page: a colour that gathers toward the edges (a shadow closing
// in, a red rim of pain), or, with `glow`, one that pools around a point and fades out (a
// torch's warmth). Drawn as one radial gradient, so it costs the GPU almost nothing.
Shape {
  id: vignette
  property color tint: "black"
  property real strength: 0.5        // how strong at its fullest, 0-1
  property real reach: 0.6           // where it starts, as a share of the radius (edges)
  property bool glow: false          // pool around the centre instead of the edges
  property real centerX: width / 2
  property real centerY: height / 2
  property real radius: Math.hypot(width, height) * 0.62

  readonly property color clear: Qt.rgba(tint.r, tint.g, tint.b, 0)
  readonly property color full: Qt.rgba(tint.r, tint.g, tint.b, Math.max(0, Math.min(1, strength)))

  visible: strength > 0.002
  preferredRendererType: Shape.CurveRenderer

  ShapePath {
    strokeWidth: -1
    strokeColor: "transparent"
    fillGradient: RadialGradient {
      centerX: vignette.centerX
      centerY: vignette.centerY
      centerRadius: vignette.radius
      focalX: vignette.centerX
      focalY: vignette.centerY
      GradientStop { position: 0.0; color: vignette.glow ? vignette.full : vignette.clear }
      GradientStop { position: vignette.reach; color: vignette.glow ? Qt.rgba(vignette.tint.r, vignette.tint.g, vignette.tint.b, vignette.strength * 0.35) : vignette.clear }
      GradientStop { position: 1.0; color: vignette.glow ? vignette.clear : vignette.full }
    }
    startX: 0; startY: 0
    PathLine { x: vignette.width; y: 0 }
    PathLine { x: vignette.width; y: vignette.height }
    PathLine { x: 0; y: vignette.height }
    PathLine { x: 0; y: 0 }
  }
}
