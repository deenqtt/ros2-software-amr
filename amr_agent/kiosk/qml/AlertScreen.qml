import QtQuick
import "."

// Low battery, error, emergency stop. One colour per severity, readable from
// across the room.
Column {
    id: alert
    property real u: 8
    property real t: 1
    property string kind: "error"
    spacing: 2.4 * u

    readonly property color tone: kind === "lowbat" ? Theme.warn : kind === "estop" ? "#b91c1c" : "#ff8080"

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 22 * alert.u
        height: width
        radius: width / 2
        color: alert.kind === "estop" ? "white" : Qt.rgba(alert.tone.r, alert.tone.g, alert.tone.b, 0.14)
        Icon {
            anchors.centerIn: parent
            name: alert.kind === "lowbat" ? "battery-low" : alert.kind === "estop" ? "stop" : "help"
            color: alert.tone
            stroke: alert.kind === "estop" ? 2.2 : 1.5
            size: 13 * alert.u
        }
    }
    Item { width: 1; height: 1.2 * alert.u }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: kiosk.title
        color: Theme.ink
        font.family: fontFamily
        font.pixelSize: 8.4 * alert.u * alert.t
        font.weight: Font.ExtraBold
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(implicitWidth, 110 * alert.u)
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: kiosk.subtitle
        color: alert.kind === "lowbat" ? "#e9d7a3" : alert.kind === "estop" ? "white" : "#f1c0c0"
        font.family: fontFamily
        font.pixelSize: 4 * alert.u * alert.t
        font.weight: Font.Medium
        lineHeight: 1.2
    }
}
