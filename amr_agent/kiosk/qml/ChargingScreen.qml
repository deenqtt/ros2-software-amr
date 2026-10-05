import QtQuick
import "."

// The face asleep above a battery that fills.
Column {
    id: charging
    property real u: 8
    property real t: 1
    spacing: 2.4 * u

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 12 * charging.u
        bottomPadding: 3 * charging.u
        Repeater {
            model: 2
            Rectangle {
                width: 13 * charging.u
                height: 2.2 * charging.u
                radius: height / 2
                color: Theme.eye
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 1600; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.85; duration: 1600; easing.type: Easing.InOutSine }
                }
            }
        }
    }

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 0.6 * charging.u
        Rectangle {
            width: 40 * charging.u
            height: 19 * charging.u
            radius: 3.6 * charging.u
            color: "transparent"
            border.color: "#c9d3ea"
            border.width: 0.9 * charging.u
            Rectangle {
                id: fill
                x: 2 * charging.u
                y: 2 * charging.u
                height: parent.height - 4 * charging.u
                width: Math.max(0, (parent.width - 4 * charging.u) * Math.max(0, kiosk.battery) / 100)
                radius: 2.2 * charging.u
                clip: true
                Behavior on width { NumberAnimation { duration: 600 } }
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Theme.okDeep }
                    GradientStop { position: 1; color: "#27dd93" }
                }
                // A sheen sweeping across: reads as "charging", not a static gauge.
                Rectangle {
                    width: parent.width * 0.5
                    height: parent.height
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: "transparent" }
                        GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.4) }
                        GradientStop { position: 1; color: "transparent" }
                    }
                    NumberAnimation on x {
                        loops: Animation.Infinite
                        from: -fill.width * 0.5
                        to: fill.width
                        duration: 1800
                        easing.type: Easing.InOutSine
                    }
                }
            }
            Icon { anchors.centerIn: parent; name: "bolt"; color: "white"; size: 10 * charging.u }
        }
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 1.8 * charging.u
            height: 7 * charging.u
            radius: 0.9 * charging.u
            color: "#c9d3ea"
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        topPadding: charging.u
        text: Math.max(0, kiosk.battery) + "%"
        color: Theme.ok
        font.family: fontFamily
        font.pixelSize: 9 * charging.u
        font.weight: Font.ExtraBold
        font.features: { "tnum": 1 }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: kiosk.title
        color: Theme.ink
        font.family: fontFamily
        font.pixelSize: 5 * charging.u * charging.t
        font.weight: Font.ExtraBold
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: kiosk.subtitle
        color: Theme.muted
        font.family: fontFamily
        font.pixelSize: 3 * charging.u * charging.t
        font.weight: Font.Medium
    }
}
