import QtQuick

// A track as a line of text: HP  ██████████░░░░  9/14
Text {
  id: meter
  property var theme
  property string label: ""
  property int value: 0
  property int maximum: 1
  property int cells: 14

  readonly property int filled: Math.max(0, Math.min(cells, Math.round(cells * value / Math.max(1, maximum))))
  readonly property bool low: value * 4 <= maximum

  textFormat: Text.StyledText
  font.family: theme.mono
  font.pixelSize: theme.small
  color: theme.text
  text: "<span style=\"color:" + theme.dim + "\">" + label.toUpperCase() + "</span>&nbsp;"
    + "<span style=\"color:" + (low ? theme.urgent : theme.accent) + "\">" + "█".repeat(filled) + "</span>"
    + "<span style=\"color:" + theme.faint + "\">" + "░".repeat(cells - filled) + "</span>"
    + "&nbsp;" + value + "/" + maximum

}
