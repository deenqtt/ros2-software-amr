import QtQuick
import QtQuick.Shapes
import QtQuick.Effects
import "."

// Arrived at a stop that waits for "Sudah diambil". The most important screen:
// one message, one button, nothing else to read. Landscape: what arrived on
// the left, the action on the right. Portrait: stacked, button at thumb height.
Item {
    id: arrived
    property real u: 8
    property real t: 1
    readonly property bool portrait: height > width

    // A green wash behind the order.
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: arrived.portrait ? Gradient.Vertical : Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(31 / 255, 207 / 255, 134 / 255, 0.12) }
            GradientStop { position: 0.6; color: Qt.rgba(31 / 255, 207 / 255, 134 / 255, 0) }
        }
    }

    Grid {
        id: layout
        anchors.centerIn: parent
        anchors.verticalCenterOffset: arrived.portrait ? 6 * arrived.u : 0
        columns: arrived.portrait ? 1 : 2
        columnSpacing: 7 * arrived.u
        rowSpacing: 6 * arrived.u
        verticalItemAlignment: Grid.AlignVCenter
        horizontalItemAlignment: arrived.portrait ? Grid.AlignHCenter : Grid.AlignLeft

        Column {
            id: info
            width: arrived.portrait ? arrived.width - 12 * arrived.u : Math.min(62 * arrived.u, arrived.width * 0.42)
            spacing: 1.6 * arrived.u

            Rectangle {
                id: badge
                anchors.horizontalCenter: arrived.portrait ? parent.horizontalCenter : undefined
                width: 15 * arrived.u
                height: width
                radius: 4.4 * arrived.u
                color: Qt.rgba(31 / 255, 207 / 255, 134 / 255, 0.14)
                border.color: Qt.rgba(31 / 255, 207 / 255, 134 / 255, 0.35)
                Icon { anchors.centerIn: parent; name: "cloche"; color: Theme.ok; size: 9 * arrived.u }
                transform: Translate { id: bob }
                SequentialAnimation {
                    running: true
                    loops: Animation.Infinite
                    NumberAnimation { target: bob; property: "y"; to: -1.2 * arrived.u; duration: 900; easing.type: Easing.InOutSine }
                    NumberAnimation { target: bob; property: "y"; to: 0; duration: 900; easing.type: Easing.InOutSine }
                }
            }
            Item { width: 1; height: 1.6 * arrived.u }
            Text {
                width: parent.width
                horizontalAlignment: arrived.portrait ? Text.AlignHCenter : Text.AlignLeft
                text: kiosk.t.arrived_kicker
                color: "#b7e9d2"
                font.family: fontFamily
                font.pixelSize: 3.8 * arrived.u * arrived.t
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                horizontalAlignment: arrived.portrait ? Text.AlignHCenter : Text.AlignLeft
                text: kiosk.place
                color: Theme.ink
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: 6 * arrived.u
                font.family: fontFamily
                font.pixelSize: 15 * arrived.u * arrived.t
                font.weight: Font.ExtraBold
                font.letterSpacing: -0.6 * arrived.u
                lineHeight: 0.95
            }
            Text {
                width: parent.width
                horizontalAlignment: arrived.portrait ? Text.AlignHCenter : Text.AlignLeft
                wrapMode: Text.WordWrap
                text: kiosk.t.arrived_hint
                color: Theme.muted
                font.family: fontFamily
                font.pixelSize: 3.2 * arrived.u * arrived.t
                font.weight: Font.Medium
            }
        }

        Column {
            width: arrived.portrait ? arrived.width - 12 * arrived.u : Math.min(70 * arrived.u, arrived.width * 0.42)
            spacing: 3 * arrived.u

            // The button.
            Rectangle {
                id: button
                width: parent.width
                height: 24 * arrived.u
                radius: 6 * arrived.u
                scale: press.pressed ? 0.97 : 1
                Behavior on scale { NumberAnimation { duration: 110 } }
                gradient: Gradient {
                    GradientStop { position: 0; color: press.pressed ? "#22c682" : "#27dd93" }
                    GradientStop { position: 1; color: press.pressed ? "#0f8f56" : Theme.okDeep }
                }
                // Breathing glow, so the eye goes to it first.
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: Theme.ok
                    shadowBlur: 1.0
                    shadowOpacity: 0.35 + glow.value * 0.1
                    shadowVerticalOffset: 1.5 * arrived.u
                    shadowHorizontalOffset: 0
                    autoPaddingEnabled: true
                }
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 0.9 * arrived.u
                    radius: parent.radius
                    color: Qt.rgba(0, 0, 0, 0.16)
                }
                Row {
                    anchors.centerIn: parent
                    spacing: 3 * arrived.u
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 12 * arrived.u
                        height: width
                        radius: width / 2
                        color: Qt.rgba(1, 1, 1, 0.22)
                        Icon { anchors.centerIn: parent; name: "check"; color: "white"; stroke: 2.4; size: 7.4 * arrived.u }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: kiosk.t.confirm
                        color: "white"
                        font.family: fontFamily
                        font.pixelSize: 6.4 * arrived.u * arrived.t
                        font.weight: Font.ExtraBold
                    }
                }
                MouseArea { id: press; anchors.fill: parent; onClicked: kiosk.confirm() }
            }

            // Countdown: the robot will not wait forever, and says so.
            Rectangle {
                id: countdownBox
                width: parent.width
                height: 12.2 * arrived.u
                radius: 3 * arrived.u
                color: Theme.bgSoft
                border.color: Theme.line
                visible: kiosk.confirmRemaining >= 0
                readonly property bool ending: kiosk.confirmRemaining >= 0 && kiosk.confirmRemaining <= 30
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 1.6 * arrived.u
                    spacing: 2 * arrived.u
                    Item {
                        width: 9 * arrived.u
                        height: width
                        Shape {
                            anchors.fill: parent
                            preferredRendererType: Shape.CurveRenderer
                            ShapePath {
                                strokeColor: Theme.bgRaised
                                strokeWidth: 0.75 * arrived.u
                                fillColor: "transparent"
                                PathAngleArc { centerX: 4.5 * arrived.u; centerY: centerX; radiusX: 4 * arrived.u; radiusY: radiusX; startAngle: 0; sweepAngle: 360 }
                            }
                            ShapePath {
                                strokeColor: countdownBox.ending ? Theme.warn : Theme.ok
                                strokeWidth: 0.75 * arrived.u
                                fillColor: "transparent"
                                capStyle: ShapePath.RoundCap
                                PathAngleArc {
                                    centerX: 4.5 * arrived.u
                                    centerY: centerX
                                    radiusX: 4 * arrived.u
                                    radiusY: radiusX
                                    startAngle: -90
                                    sweepAngle: kiosk.confirmTimeout > 0 ? 360 * kiosk.confirmRemaining / kiosk.confirmTimeout : 360
                                    Behavior on sweepAngle { NumberAnimation { duration: 900 } }
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            text: kiosk.countdownClock
                            color: countdownBox.ending ? Theme.warn : Theme.ink
                            font.family: fontFamily
                            font.pixelSize: 2.6 * arrived.u
                            font.weight: Font.ExtraBold
                            font.features: { "tnum": 1 }
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: kiosk.countdownText
                        color: Theme.muted
                        font.family: fontFamily
                        font.pixelSize: 2.7 * arrived.u * arrived.t
                        font.weight: Font.Medium
                    }
                }
            }
        }
    }

    QtObject {
        id: glow
        property real value: 0
        property var anim: SequentialAnimation {
            running: true
            loops: Animation.Infinite
            NumberAnimation { target: glow; property: "value"; to: 3; duration: 1200; easing.type: Easing.InOutSine }
            NumberAnimation { target: glow; property: "value"; to: 0; duration: 1200; easing.type: Easing.InOutSine }
        }
    }
}
