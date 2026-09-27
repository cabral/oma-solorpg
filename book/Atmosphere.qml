import QtQuick

// The weather of the page, from the state of the game. A faint shadow at the edges always,
// as a lamp throws on a book. In a dark place with nothing burning the shadow closes in
// and breathes; a torch pushes it back and pools warm light by the hero, flickering. While
// the hero is dying a red rim beats like a heart, slower as they weaken. A hit flashes red
// at the edges, a Dragon gold. It lies over the page and takes no clicks.
Item {
  id: air
  property var theme
  property var game: null
  // Where the hero stands on the page (the torch's light pools there).
  property real heroX: width * 0.2
  property real heroY: height * 0.3

  readonly property var pc: game ? game.pc : null
  readonly property bool lit: !!(game && game.light)
  readonly property bool dark: !!(game && game.dark) && !lit
  readonly property bool dying: !!(pc && pc.dying)
  readonly property bool dead: !!(pc && pc.dead)
  // How much of its burning the torch has left, 0-1: it dims as it goes.
  readonly property real fuel: lit ? Math.max(0.15, Math.min(1, game.light.left / Math.max(1, game.light.burns))) : 0

  function flash(kind) {
    flashRim.tint = kind === "dragon" ? theme.gold : theme.urgent
    flashRim.peak = kind === "dragon" ? 0.45 : kind === "demon" ? 0.6 : 0.5
    flashing.restart()
  }

  // The book's own shadow.
  Vignette { anchors.fill: parent; tint: "black"; strength: 0.28; reach: 0.55 }

  // Darkness: it closes in and breathes. Lighting something pushes it back.
  Vignette {
    id: darkness
    anchors.fill: parent
    tint: "black"
    reach: 0.25
    property real depth: air.dark ? 0.82 : air.lit ? 0.35 * (1.2 - air.fuel) : 0
    strength: depth
    Behavior on depth { NumberAnimation { duration: 1800; easing.type: Easing.InOutQuad } }
    SequentialAnimation on reach {
      running: air.dark && air.visible
      loops: Animation.Infinite
      NumberAnimation { to: 0.18; duration: 3200; easing.type: Easing.InOutSine }
      NumberAnimation { to: 0.28; duration: 3800; easing.type: Easing.InOutSine }
    }
  }

  // The torch: warm light by the hero, flickering, dimmer as it burns down.
  Vignette {
    id: torchlight
    anchors.fill: parent
    glow: true
    tint: air.theme.gold
    centerX: air.heroX
    centerY: air.heroY
    radius: Math.max(air.width, air.height) * (0.45 + 0.25 * air.fuel)
    reach: 0.4
    property real flame: 1.0
    strength: air.lit ? 0.16 * air.fuel * flame : 0
    Behavior on strength { NumberAnimation { duration: 140 } }
    Timer {
      interval: 110
      repeat: true
      running: air.lit && air.visible
      onTriggered: {
        torchlight.flame = 0.75 + Math.random() * 0.35
        interval = 80 + Math.random() * 160
      }
    }
  }

  // Dying: a red rim that beats like a heart, lub-dub, slower with every failure.
  Vignette {
    id: heart
    anchors.fill: parent
    tint: air.theme.urgent
    reach: 0.45
    property real beat: 0
    strength: air.dying ? 0.12 + beat * 0.38 : air.dead ? 0.1 : 0
    readonly property int pause: air.pc && air.pc.dying ? 500 + air.pc.dying.failures * 350 : 600
    SequentialAnimation on beat {
      running: air.dying && air.visible
      loops: Animation.Infinite
      NumberAnimation { to: 1; duration: 110; easing.type: Easing.OutQuad }
      NumberAnimation { to: 0.35; duration: 160; easing.type: Easing.InQuad }
      NumberAnimation { to: 0.8; duration: 110; easing.type: Easing.OutQuad }
      NumberAnimation { to: 0; duration: 420; easing.type: Easing.InQuad }
      PauseAnimation { duration: heart.pause }
    }
  }

  // A hit, or a Dragon: a flash at the edges.
  Vignette {
    id: flashRim
    anchors.fill: parent
    reach: 0.4
    property real peak: 0.5
    property real level: 0
    tint: air.theme.urgent
    strength: level
    SequentialAnimation {
      id: flashing
      NumberAnimation { target: flashRim; property: "level"; to: flashRim.peak; duration: 90; easing.type: Easing.OutQuad }
      NumberAnimation { target: flashRim; property: "level"; to: 0; duration: 900; easing.type: Easing.InQuad }
    }
  }
}
