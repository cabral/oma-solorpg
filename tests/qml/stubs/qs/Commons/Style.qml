pragma Singleton
import QtQuick

// Stand-in for omarchy-shell's Style for offscreen checks.
QtObject {
  readonly property real cornerRadius: 4
  readonly property real gapsOut: 10
  readonly property QtObject font: QtObject {
    readonly property string family: "DejaVu Sans Mono"
    readonly property real caption: 10
    readonly property real bodySmall: 11
    readonly property real body: 12
    readonly property real subtitle: 13
    readonly property real title: 14
    readonly property real heading: 16
    readonly property real display: 24
  }
  readonly property QtObject spacing: QtObject {
    readonly property real controlPaddingX: 8
    readonly property real controlPaddingY: 4
  }
  function space(px) { return px }
}
