import QtQuick

// Momentum as a line of text. It runs below zero, so the bar has a zero in it:
//   MOMENTUM  ░░░░░░│██░░░░░░░░  +2
// Cells above what the hero's impacts leave of the ceiling are dotted out.
Text {
  id: meter
  property var theme
  property var track: ({ value: 0, max: 10 })   // the hero's momentum: value, max (as impacts leave it), reset
  property var spec: ({ min: -6, max: 10 })     // the game's range: labels.momentum

  function cell(color, glyph) {
    return "<span style=\"color:" + color + "\">" + glyph + "</span>"
  }

  function bar() {
    var out = ""
    for (var n = spec.min; n <= -1; n++)
      out += track.value < 0 && n >= track.value ? cell(theme.urgent, "█") : cell(theme.faint, "░")
    out += cell(theme.dim, "│")
    for (n = 1; n <= spec.max; n++)
      out += n > track.max ? cell(theme.faint, "·") : track.value >= n ? cell(theme.accent, "█") : cell(theme.faint, "░")
    return out
  }

  textFormat: Text.StyledText
  font.family: theme.mono
  font.pixelSize: theme.small
  color: theme.text
  text: "<span style=\"color:" + theme.dim + "\">MOMENTUM</span>&nbsp;" + bar() + "&nbsp;"
    + (track.value > 0 ? "+" : "") + track.value
}
