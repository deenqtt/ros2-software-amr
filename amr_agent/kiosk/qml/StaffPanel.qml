import QtQuick
import "."

// Staff only: opened by holding the top-left corner, then a PIN. Hidden from
// guests, who lean on screens and press whatever is there.
Rectangle {
    id: staff
    property real u: 8
    property bool unlocked: false
    property string pin: ""
    property bool showInfo: false

    color: Qt.rgba(4 / 255, 7 / 255, 13 / 255, 0.92)
    visible: false

    function open() { pin = ""; unlocked = false; showInfo = false; visible = true }
    function close() { visible = false }
    function press(key) {
        if (key === "back") pin = pin.slice(0, -1)
        else if (pin.length < 4) pin += key
        if (pin.length === 4) {
            if (kiosk.checkPin(pin)) unlocked = true
            else { shake.restart(); pin = "" }
        }
    }

    MouseArea { anchors.fill: parent }  // swallow touches behind the card

    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.9, 64 * staff.u)
        height: content.height + 8 * staff.u
        radius: 4 * staff.u
        color: Theme.bgSoft
        border.color: Theme.line

        Column {
            id: content
            anchors.centerIn: parent
            width: parent.width - 8 * staff.u
            spacing: 1.6 * staff.u

            Row {
                anchors.horizontalCenter: staff.unlocked ? undefined : parent.horizontalCenter
                spacing: 1.4 * staff.u
                bottomPadding: 1.4 * staff.u
                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: staff.unlocked ? "sliders" : "lock"
                    color: Theme.muted
                    size: 4 * staff.u
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: staff.unlocked ? kiosk.t.menu_title : kiosk.t.pin_title
                    color: Theme.ink
                    font.family: fontFamily
                    font.pixelSize: 3.6 * staff.u
                    font.weight: Font.Bold
                }
            }

            // ── PIN ───────────────────────────────────────────────────────
            Row {
                id: dots
                visible: !staff.unlocked
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 2.6 * staff.u
                bottomPadding: 1.8 * staff.u
                transform: Translate { id: shakeX }
                Repeater {
                    model: 4
                    Rectangle {
                        width: 2.8 * staff.u
                        height: width
                        radius: width / 2
                        color: index < staff.pin.length ? Theme.ink : "transparent"
                        border.width: 0.35 * staff.u
                        border.color: shake.running ? Theme.fault : index < staff.pin.length ? Theme.ink : Theme.muted
                    }
                }
                SequentialAnimation {
                    id: shake
                    NumberAnimation { target: shakeX; property: "x"; to: -2 * staff.u; duration: 90 }
                    NumberAnimation { target: shakeX; property: "x"; to: 2 * staff.u; duration: 180 }
                    NumberAnimation { target: shakeX; property: "x"; to: 0; duration: 90 }
                }
            }
            Grid {
                visible: !staff.unlocked
                columns: 3
                spacing: 1.6 * staff.u
                Repeater {
                    model: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "close"]
                    Rectangle {
                        width: (content.width - 3.2 * staff.u) / 3
                        height: 11 * staff.u
                        radius: 2.6 * staff.u
                        color: keyArea.pressed ? "#24345a" : modelData === "back" || modelData === "close" ? "transparent" : Theme.bgRaised
                        border.color: modelData === "back" || modelData === "close" ? "transparent" : Theme.line
                        Text {
                            anchors.centerIn: parent
                            visible: modelData.length === 1
                            text: modelData
                            color: Theme.ink
                            font.family: fontFamily
                            font.pixelSize: 4.2 * staff.u
                            font.weight: Font.Bold
                        }
                        Icon {
                            anchors.centerIn: parent
                            visible: modelData.length > 1
                            name: modelData === "back" ? "backspace" : "x"
                            color: Theme.muted
                            size: 4.6 * staff.u
                        }
                        MouseArea {
                            id: keyArea
                            anchors.fill: parent
                            onClicked: modelData === "close" ? staff.close() : staff.press(modelData)
                        }
                    }
                }
            }

            // ── Menu ──────────────────────────────────────────────────────
            Repeater {
                model: staff.unlocked ? [
                    { action: "continue", icon: "play-forward", label: kiosk.t.menu_continue, enabled: kiosk.screen === "arrived" },
                    { action: "large", icon: "text-size", label: kiosk.t.menu_large, enabled: true },
                    { action: "info", icon: "info", label: kiosk.t.menu_info, enabled: true }
                ] : []
                Rectangle {
                    width: content.width
                    height: 10 * staff.u
                    radius: 2.6 * staff.u
                    color: itemArea.pressed ? "#24345a" : Theme.bgRaised
                    border.color: Theme.line
                    opacity: modelData.enabled ? 1 : 0.4
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 3.4 * staff.u
                        spacing: 2.4 * staff.u
                        Icon { anchors.verticalCenter: parent.verticalCenter; name: modelData.icon; color: Theme.muted; size: 4 * staff.u }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            color: Theme.ink
                            font.family: fontFamily
                            font.pixelSize: 3.2 * staff.u
                            font.weight: Font.DemiBold
                        }
                    }
                    // The large-text switch.
                    Rectangle {
                        visible: modelData.action === "large"
                        anchors.right: parent.right
                        anchors.rightMargin: 3 * staff.u
                        anchors.verticalCenter: parent.verticalCenter
                        width: 7 * staff.u
                        height: 4 * staff.u
                        radius: height / 2
                        color: kiosk.largeText ? Theme.accent : Theme.bg
                        border.color: Theme.line
                        Rectangle {
                            width: 2.9 * staff.u
                            height: width
                            radius: width / 2
                            anchors.verticalCenter: parent.verticalCenter
                            x: kiosk.largeText ? parent.width - width - 0.5 * staff.u : 0.5 * staff.u
                            color: kiosk.largeText ? "white" : Theme.muted
                            Behavior on x { NumberAnimation { duration: 180 } }
                        }
                    }
                    MouseArea {
                        id: itemArea
                        anchors.fill: parent
                        enabled: modelData.enabled
                        onClicked: {
                            if (modelData.action === "continue") { kiosk.confirm(); staff.close() }
                            else if (modelData.action === "large") kiosk.toggleLarge()
                            else staff.showInfo = !staff.showInfo
                        }
                    }
                }
            }
            Rectangle {
                visible: staff.unlocked && staff.showInfo
                width: content.width
                height: info.implicitHeight + 4 * staff.u
                radius: 2 * staff.u
                color: Theme.bg
                border.color: Theme.line
                Text {
                    id: info
                    anchors.centerIn: parent
                    width: parent.width - 4.8 * staff.u
                    text: kiosk.techInfo
                    color: "#a9bce2"
                    font.family: "monospace"
                    font.pixelSize: 2.3 * staff.u
                    lineHeight: 1.4
                }
            }
            Text {
                visible: staff.unlocked
                width: content.width
                topPadding: 1.6 * staff.u
                horizontalAlignment: Text.AlignHCenter
                text: kiosk.t.menu_close
                color: Theme.muted
                font.family: fontFamily
                font.pixelSize: 3 * staff.u
                font.weight: Font.DemiBold
                MouseArea { anchors.fill: parent; anchors.margins: -2 * staff.u; onClicked: staff.close() }
            }
        }
    }
}
