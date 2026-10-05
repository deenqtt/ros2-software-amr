import QtQuick
import "."

// Where the robot has been, is going, and will go.
Row {
    id: routeBar
    property real u: 8
    property real t: 1
    property var stops: []
    property int current: -1
    property bool currentDone: false

    Repeater {
        model: routeBar.stops
        Item {
            readonly property bool done: index < routeBar.current || (index === routeBar.current && routeBar.currentDone)
            readonly property bool active: index === routeBar.current && !routeBar.currentDone
            // Each stop's connector reaches back under the previous stop's
            // dot; earlier stops on top keep the dots whole.
            z: -index
            width: 15 * routeBar.u
            height: 7 * routeBar.u

            // The connector from the previous stop.
            Rectangle {
                visible: index > 0
                x: -width / 2
                y: 1.3 * routeBar.u
                width: parent.width
                height: 0.4 * routeBar.u
                color: parent.done || parent.active ? Theme.ok : Theme.bgRaised
            }
            Rectangle {
                id: dot
                anchors.horizontalCenter: parent.horizontalCenter
                width: 3 * routeBar.u
                height: width
                radius: width / 2
                color: parent.done ? Theme.ok : parent.active ? Theme.accent : Theme.bg
                border.width: 0.4 * routeBar.u
                border.color: parent.done ? Theme.ok : parent.active ? Theme.accent : Theme.bgRaised
                Icon {
                    anchors.centerIn: parent
                    visible: dot.parent.done
                    name: "check"
                    color: Theme.bg
                    stroke: 3
                    size: 2 * routeBar.u
                }
                // A soft pulse round the stop it is driving to.
                Rectangle {
                    anchors.centerIn: parent
                    visible: dot.parent.active
                    width: parent.width + pulse.value * routeBar.u
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: 0.8 * routeBar.u
                    border.color: Qt.rgba(47 / 255, 107 / 255, 1, 0.3 * (1 - pulse.value / 3))
                }
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: dot.bottom
                anchors.topMargin: routeBar.u
                text: modelData
                color: parent.active ? Theme.ink : Theme.muted
                font.family: fontFamily
                font.pixelSize: 2.3 * routeBar.u * routeBar.t
                font.weight: Font.DemiBold
            }
        }
    }
    QtObject {
        id: pulse
        property real value: 0
        property var anim: SequentialAnimation {
            running: true
            loops: Animation.Infinite
            NumberAnimation { target: pulse; property: "value"; from: 0; to: 3; duration: 1400; easing.type: Easing.OutQuad }
        }
    }
}
