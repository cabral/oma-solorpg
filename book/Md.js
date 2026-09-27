.pragma library

// The GM's words as rich text for a Text item. Only a small, safe subset of Markdown:
// paragraphs, line breaks, *italic*, **bold**, `mono`, "- " bullets and "#" headings.
// Everything else is escaped, so no images, links or HTML ever come through from a
// model or a shared adventure.

function escape(text) {
  return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

function inline(text, mono) {
  return escape(text)
    .replace(/`([^`]+)`/g, function(_, code) { return "<span style=\"font-family:'" + mono + "'\">" + code + "</span>" })
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<i>$2</i>")
    .replace(/(^|[^_\w])_([^_\n]+)_(?!\w)/g, "$1<i>$2</i>")
}

// A paragraph shorter than this (in characters) can fit on one line of the Book's column,
// which is at most about 75 wide: too short to wrap around a letter two lines tall.
var DROP_AFTER = 90

// `initial`: a colour for an illuminated first letter (the first words of a scene), or "";
// `prose`: the size of the text around it. The letter drops two lines into the paragraph,
// the text wrapping around it: a floated table is the one float Qt's rich text has. The
// letter is three times the text, so it sits on the second line; its box is held to 2.6,
// which is more than one line and less than two for any serif's line spacing. An opening
// too short to wrap around it gets the colour alone.
function render(text, mono, initial, prose) {
  var blocks = String(text || "").replace(/\r/g, "").split(/\n\s*\n/)
  var html = []
  for (var b = 0; b < blocks.length; b++) {
    var lines = blocks[b].split("\n").filter(function(l) { return l.trim() !== "" })
    if (lines.length === 0) continue
    var out = lines.map(function(line) {
      var heading = /^#{1,6}\s+/.test(line)
      var bullet = /^\s*[-*]\s+/.test(line)
      var body = inline(line.replace(/^#{1,6}\s+/, "").replace(/^\s*[-*]\s+/, ""), mono)
      return heading ? "<b>" + body + "</b>" : bullet ? "&nbsp;&nbsp;•&nbsp;" + body : body
    }).join("<br>")
    var lead = ""
    var first = initial && html.length === 0 ? out.match(/^["'“‘]?[A-Za-zÀ-ɏ]/) : null
    if (first && blocks[b].trim().length >= DROP_AFTER) {
      var size = prose || 16
      lead = "<table style=\"float: left\" cellpadding=\"0\" cellspacing=\"0\" height=\"" + Math.round(size * 2.6) + "\"><tr>"
        + "<td style=\"font-size:" + Math.round(size * 3) + "px; color:" + initial + "; padding-right:" + Math.round(size * 0.4) + "px\">"
        + first[0] + "</td></tr></table>"
      out = out.slice(first[0].length)
    } else if (first) {
      out = "<span style=\"color:" + initial + "\">" + first[0] + "</span>" + out.slice(first[0].length)
    }
    html.push(lead + "<p>" + out + "</p>")
  }
  return html.join("")
}
