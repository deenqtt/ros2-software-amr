pragma Singleton
import QtQuick

// Colours and timings, from docs/design/kiosk-mockup/styles.css. Severity colours follow
// the usual industrial convention: red danger, amber caution, blue information.
QtObject {
    readonly property color bg: "#070b14"
    readonly property color bgSoft: "#111a2c"
    readonly property color bgRaised: "#17223a"
    readonly property color line: Qt.rgba(160 / 255, 184 / 255, 230 / 255, 0.14)
    readonly property color ink: "#f1f5ff"
    readonly property color muted: "#8d9ab8"
    readonly property color eye: "#62e3ff"
    readonly property color eyeDeep: "#1ea7d8"
    readonly property color eyeHi: "#c9f6ff"
    readonly property color amber: "#ffd166"
    readonly property color amberDeep: "#e09a00"
    readonly property color accent: "#2f6bff"
    readonly property color ok: "#1fcf86"
    readonly property color okDeep: "#13a866"
    readonly property color warn: "#f5b301"
    readonly property color fault: "#ef4444"

    // The screen behind the face. The eyelids are drawn in this colour, so it
    // must be one flat colour per screen.
    function screenColor(screen) {
        switch (screen) {
        case "blocked": return "#161104"
        case "lowbat": return "#1a1300"
        case "error": return "#1d0809"
        case "estop": return "#b91c1c"
        default: return bg
        }
    }
}
