import QtQuick
import QtQuick.Shapes
import QtQuick.Effects
import "."

// The robot's face: two blocks of light with lids in the screen's colour
// sliding over them (Cozmo-style), so every mood is the same shape cut
// differently and moods blend instead of popping. "happy" swaps the blocks for
// upturned arcs ^ ^.
Item {
    id: face

    property real u: 8
    property string mood: "neutral"
    property color screenColor: Theme.bg
    // Where the eyes look, -1..1. Driven by the glance timer below or by a turn.
    property real lookX: 0
    property real lookY: 0
    property string turn: ""
    property bool wandering: true

    signal poked()

    readonly property bool worried: mood === "worried"
    readonly property bool happy: mood === "happy"
    readonly property color eyeColor: worried ? Theme.amber : Theme.eye
    readonly property color eyeDeep: worried ? Theme.amberDeep : Theme.eyeDeep
    readonly property color eyeHi: worried ? "#fff4cf" : Theme.eyeHi

    // Lid heights as a fraction of the eye, per mood.
    readonly property real lidTop: ({ focused: 0.2, worried: 0.42, annoyed: 0.46, sleepy: 0.56 })[mood] || 0
    readonly property real lidBottom: ({ eager: 0.1, annoyed: 0.14, sleepy: 0.08 })[mood] || 0
    readonly property real lidTilt: worried ? 16 : 0
    readonly property real eyeScale: mood === "eager" ? 1.08 : happy ? 1.04 : 1

    implicitWidth: eyes.width + 16 * u
    implicitHeight: 34 * u

    // A slow float, so the robot reads as alive even when nothing happens.
    property real floatY: 0
    SequentialAnimation on floatY {
        loops: Animation.Infinite
        NumberAnimation { to: -1.2 * face.u; duration: 2750; easing.type: Easing.InOutSine }
        NumberAnimation { to: 0; duration: 2750; easing.type: Easing.InOutSine }
    }

    // Blink every 2–6 s at random; now and then twice. A steady rhythm reads as a machine.
    property real open: 1
    SequentialAnimation {
        id: blink
        NumberAnimation { target: face; property: "open"; to: 0.08; duration: 70; easing.type: Easing.InQuad }
        NumberAnimation { target: face; property: "open"; to: 1; duration: 110; easing.type: Easing.OutQuad }
    }
    Timer {
        id: blinkTimer
        interval: 3000
        running: true
        onTriggered: {
            if (!face.happy && face.mood !== "annoyed") {
                blink.restart()
                if (Math.random() < 0.25) doubleBlink.start()
            }
            interval = 2000 + Math.random() * 4000
            restart()
        }
    }
    Timer { id: doubleBlink; interval: 250; onTriggered: blink.restart() }

    // Glances: around the room when idle, at the road when driving, side to
    // side when looking for a way round.
    Timer {
        interval: 2200
        running: face.wandering
        repeat: true
        onTriggered: {
            interval = 1400 + Math.random() * 2600
            if (face.turn !== "") return
            if (face.mood === "neutral") {
                face.lookX = (Math.random() * 2 - 1) * 0.9
                face.lookY = (Math.random() * 2 - 1) * 0.5
            } else if (face.mood === "focused" || face.mood === "eager") {
                face.lookX = Math.random() < 0.3 ? (Math.random() < 0.5 ? -0.5 : 0.5) : 0
                face.lookY = -0.1
            } else if (face.worried) {
                face.lookX = Math.random() < 0.5 ? -0.85 : 0.85
                face.lookY = 0
            } else {
                face.lookX = 0
                face.lookY = 0
            }
        }
    }
    onTurnChanged: if (turn !== "") { lookX = turn === "left" ? -0.9 : 0.9; lookY = -0.1 }

    Behavior on lookX { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
    Behavior on lookY { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }

    component Eye: Item {
        id: eye
        property bool isLeft: true
        width: 18 * face.u
        height: 25 * face.u

        transform: [
            Scale {
                origin.x: eye.width / 2
                origin.y: eye.height / 2
                xScale: face.eyeScale
                yScale: face.eyeScale * (face.happy ? 1 : face.open)
            },
            Translate { x: face.lookX * 4.5 * face.u; y: face.lookY * 3 * face.u + face.floatY }
        ]

        // Glow: the eye's own shape, blurred, behind it.
        Rectangle {
            anchors.fill: parent
            radius: 6.5 * face.u
            color: face.eyeColor
            opacity: face.happy ? 0 : 0.55
            Behavior on opacity { NumberAnimation { duration: 200 } }
            layer.enabled: true
            layer.effect: MultiEffect {
                blurEnabled: true
                blur: 1.0
                blurMax: 48
                autoPaddingEnabled: true
            }
        }

        // The rounded shape everything inside the eye is cut to. A plain
        // `clip` cuts to the rectangle, and the lids' corners would show.
        Rectangle {
            id: eyeMask
            anchors.fill: parent
            radius: 6.5 * face.u
            visible: false
            layer.enabled: true
        }

        Item {
            id: body
            anchors.fill: parent
            opacity: face.happy ? 0 : 1
            Behavior on opacity { NumberAnimation { duration: 180 } }
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: eyeMask
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: face.eyeHi }
                    GradientStop { position: 0.3; color: face.eyeColor }
                    GradientStop { position: 1; color: face.eyeDeep }
                }
            }
            Rectangle {
                width: 4 * face.u
                height: width
                radius: width / 2
                x: parent.width * 0.22
                y: parent.height * 0.16
                color: "white"
                opacity: face.lidTop > 0.4 || face.mood === "annoyed" ? 0 : 0.9
                Behavior on opacity { NumberAnimation { duration: 200 } }
            }

            // Lids.
            Rectangle {
                width: parent.width * 1.4
                x: -parent.width * 0.2
                y: -2
                height: parent.height * face.lidTop + 2
                color: face.screenColor
                transformOrigin: Item.Bottom
                rotation: eye.isLeft ? -face.lidTilt : face.lidTilt
                Behavior on height { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
                Behavior on rotation { NumberAnimation { duration: 260 } }
            }
            Rectangle {
                width: parent.width * 1.4
                x: -parent.width * 0.2
                height: parent.height * face.lidBottom + 2
                y: parent.height - height + 2
                color: face.screenColor
                Behavior on height { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
            }
        }

        // Happy: an upturned arc in place of the block.
        Shape {
            anchors.fill: parent
            opacity: face.happy ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 180 } }
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: face.eyeColor
                strokeWidth: 3.6 * face.u
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc {
                    centerX: eye.width / 2
                    centerY: eye.height * 0.62
                    radiusX: eye.width / 2 - 1.8 * face.u
                    radiusY: radiusX
                    startAngle: 205
                    sweepAngle: 130
                }
            }
        }
    }

    Row {
        id: eyes
        anchors.centerIn: parent
        spacing: 15 * face.u
        Eye { isLeft: true }
        Eye { isLeft: false }
    }

    // Blushing cheeks when happy.
    Repeater {
        model: [-1, 1]
        Rectangle {
            width: 9 * face.u
            height: 3.6 * face.u
            radius: height / 2
            color: "#ff78a0"
            opacity: face.happy ? 0.45 : 0
            x: face.width / 2 + modelData * (eyes.width / 2 + 0.5 * face.u) - width / 2 + face.lookX * 4.5 * face.u
            y: face.height / 2 + 7 * face.u + face.floatY
            Behavior on opacity { NumberAnimation { duration: 300 } }
            layer.enabled: true
            layer.effect: MultiEffect { blurEnabled: true; blur: 0.8; blurMax: 24; autoPaddingEnabled: true }
        }
    }

    MouseArea {
        anchors.fill: eyes
        anchors.margins: -4 * face.u
        onPressed: face.poked()
    }
}
