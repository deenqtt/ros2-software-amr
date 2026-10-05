import QtQuick
import QtQuick.Window
import "."

Window {
    id: window
    width: startSize.width
    height: startSize.height
    visible: true
    visibility: windowed ? Window.Windowed : Window.FullScreen
    title: "AMR Kiosk"
    color: Theme.screenColor(kiosk.screen)
    Behavior on color { ColorAnimation { duration: 400 } }

    // One unit = 1% of the short side, so the same layout serves a 7" portrait
    // panel and a 15" landscape one.
    readonly property real u: Math.min(width, height) / 100
    readonly property real t: kiosk.largeText ? 1.25 : 1
    readonly property string screen: kiosk.screen
    readonly property bool faceScreen: ["idle", "moving", "blocked", "thanks", "offline"].indexOf(screen) >= 0

    readonly property var pillStyle: ({
        idle: [Theme.bgSoft, Theme.ink, "check"],
        offline: [Theme.bgSoft, Theme.muted, "wifi-off"],
        moving: [Theme.accent, "white", "play"],
        blocked: [Theme.warn, "#1b1607", "pause"],
        arrived: [Theme.ok, "#04170e", "pin"],
        thanks: [Theme.ok, "#04170e", "check"],
        charging: [Qt.rgba(31 / 255, 207 / 255, 134 / 255, 0.16), Theme.ok, "bolt"],
        lowbat: [Theme.warn, "#1b1607", "battery-low"],
        error: [Theme.fault, "white", "help"],
        estop: ["white", "#b91c1c", "stop"]
    })

    // Emergency stop: the whole screen pulses red.
    Rectangle {
        anchors.fill: parent
        visible: window.screen === "estop"
        color: "#7a1212"
        SequentialAnimation on opacity {
            running: window.screen === "estop"
            loops: Animation.Infinite
            NumberAnimation { to: 1; duration: 600; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0; duration: 600; easing.type: Easing.InOutSine }
        }
    }

    StatusBar {
        id: statusBar
        z: 2
        width: parent.width
        u: window.u
        pillColor: window.pillStyle[window.screen][0]
        pillInk: window.pillStyle[window.screen][1]
        pillIcon: window.pillStyle[window.screen][2]
    }

    // ── The face, with what it is doing ───────────────────────────────────
    Column {
        id: stage
        visible: window.faceScreen
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -1 * window.u
        spacing: 3.2 * window.u

        Face {
            anchors.horizontalCenter: parent.horizontalCenter
            u: window.u
            mood: kiosk.mood
            screenColor: window.color
            turn: kiosk.intentText !== "" ? kiosk.intentSide : ""
            onPoked: kiosk.poke()
        }
        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 1.4 * window.u
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: kiosk.title
                color: Theme.ink
                font.family: fontFamily
                font.pixelSize: 7.2 * window.u * window.t
                font.weight: Font.ExtraBold
                font.letterSpacing: -0.15 * window.u
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: kiosk.subtitle
                color: Theme.muted
                font.family: fontFamily
                font.pixelSize: 3.6 * window.u * window.t
                font.weight: Font.Medium
            }
        }
        // Turn intent, said in the robot's own voice, in amber like an indicator.
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: kiosk.intentText !== ""
            height: 5.6 * window.u
            width: intentRow.width + 4.6 * window.u
            radius: height / 2
            color: Qt.rgba(245 / 255, 179 / 255, 1 / 255, 0.14)
            border.color: Qt.rgba(245 / 255, 179 / 255, 1 / 255, 0.4)
            Row {
                id: intentRow
                anchors.centerIn: parent
                spacing: 1.4 * window.u
                Icon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: kiosk.intentSide === "right" ? "turn-right" : "turn-left"
                    color: Theme.amber
                    stroke: 2
                    size: 4 * window.u
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        PropertyAction { value: 1 }
                        PauseAnimation { duration: 350 }
                        PropertyAction { value: 0.25 }
                        PauseAnimation { duration: 350 }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: kiosk.intentText
                    color: Theme.amber
                    font.family: fontFamily
                    font.pixelSize: 3 * window.u * window.t
                    font.weight: Font.Bold
                }
            }
        }
        RouteBar {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: kiosk.showRoute
            topPadding: window.u
            u: window.u
            t: window.t
            stops: kiosk.route
            current: kiosk.step
            currentDone: window.screen === "thanks"
        }
    }

    ArrivedScreen {
        anchors.fill: parent
        anchors.topMargin: statusBar.height
        visible: window.screen === "arrived"
        u: window.u
        t: window.t
    }

    ChargingScreen {
        anchors.centerIn: parent
        visible: window.screen === "charging"
        u: window.u
        t: window.t
    }

    AlertScreen {
        anchors.centerIn: parent
        visible: ["lowbat", "error", "estop"].indexOf(window.screen) >= 0
        kind: window.screen
        u: window.u
        t: window.t
    }

    // Staff: hold the top-left corner.
    MouseArea {
        z: 3
        width: 12 * window.u
        height: 12 * window.u
        pressAndHoldInterval: 1200
        onPressAndHold: staffPanel.open()
    }
    StaffPanel {
        id: staffPanel
        z: 4
        anchors.fill: parent
        u: window.u
    }
    Connections {
        target: kiosk
        function onStaffRequested() { staffPanel.open(); staffPanel.unlocked = true }
    }

    // Simulation keys (--mock): 1–9 jump between states, L switches language,
    // S opens the staff menu.
    Item {
        focus: true
        Keys.onPressed: (event) => {
            if (event.text === "l" || event.text === "L") kiosk.toggleLang()
            else if (event.key === Qt.Key_Escape && windowed) Qt.quit()
            else if (event.text !== "") kiosk.key(event.text)
        }
    }
}
