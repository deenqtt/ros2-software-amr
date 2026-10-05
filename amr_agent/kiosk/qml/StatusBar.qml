import QtQuick
import "."

// Small on purpose. The screen is read from 1–2 m in about two seconds, so the
// face and the one message own the space, not chrome.
Item {
    id: bar
    property real u: 8
    property color pillColor: Theme.bgSoft
    property color pillInk: Theme.ink
    property string pillIcon: "check"

    height: 7.6 * u

    Row {
        anchors.left: parent.left
        anchors.leftMargin: 3.4 * bar.u
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2 * bar.u

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: kiosk.robotName
            color: Theme.ink
            font.family: fontFamily
            font.pixelSize: 2.6 * bar.u
            font.weight: Font.ExtraBold
            font.letterSpacing: 0.05 * bar.u
        }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            height: 4 * bar.u
            width: pillRow.width + 3.2 * bar.u
            radius: height / 2
            color: bar.pillColor
            Behavior on color { ColorAnimation { duration: 300 } }
            Row {
                id: pillRow
                anchors.centerIn: parent
                spacing: 0.9 * bar.u
                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: bar.pillIcon
                    color: bar.pillInk
                    stroke: 2
                    size: 2.6 * bar.u
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: kiosk.pill
                    color: bar.pillInk
                    font.family: fontFamily
                    font.pixelSize: 2.2 * bar.u
                    font.weight: Font.Bold
                }
            }
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 3.4 * bar.u
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2 * bar.u

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            name: kiosk.linked ? "wifi" : "wifi-off"
            color: kiosk.linked ? Theme.ok : Theme.muted
            size: 2.8 * bar.u
        }
        Text {
            id: clock
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.ink
            font.family: fontFamily
            font.pixelSize: 2.6 * bar.u
            font.weight: Font.DemiBold
            font.features: { "tnum": 1 }
            function update() { text = Qt.formatTime(new Date(), "hh.mm") }
            Component.onCompleted: update()
            Timer { interval: 1000; running: true; repeat: true; onTriggered: clock.update() }
        }
        // Battery, drawn: shell, cap, fill.
        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 0.8 * bar.u
            visible: kiosk.battery >= 0
            Item {
                anchors.verticalCenter: parent.verticalCenter
                width: 5.6 * bar.u
                height: 2.8 * bar.u
                Rectangle {
                    width: parent.width - 0.7 * bar.u
                    height: parent.height
                    radius: 0.6 * bar.u
                    color: "transparent"
                    border.color: Theme.muted
                    border.width: Math.max(1, 0.25 * bar.u)
                    Rectangle {
                        x: 0.45 * bar.u
                        y: 0.45 * bar.u
                        height: parent.height - 0.9 * bar.u
                        width: Math.max(0.3 * bar.u, (parent.width - 0.9 * bar.u) * kiosk.battery / 100)
                        radius: 0.3 * bar.u
                        color: kiosk.battery <= 15 ? Theme.fault : kiosk.battery <= 30 ? Theme.warn : Theme.ok
                    }
                }
                Rectangle {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 0.4 * bar.u
                    height: 1.1 * bar.u
                    radius: 0.2 * bar.u
                    color: Theme.muted
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: kiosk.battery + "%"
                color: Theme.ink
                font.family: fontFamily
                font.pixelSize: 2.6 * bar.u
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
        }
    }
}
