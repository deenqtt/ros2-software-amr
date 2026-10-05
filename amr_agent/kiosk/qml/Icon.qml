import QtQuick

// One drawn icon in any colour, from IconProvider in kiosk_app.py.
Image {
    id: icon
    property string name: "info"
    property color color: "white"
    property real stroke: 1.5
    property real size: 24

    width: size
    height: size
    sourceSize: Qt.size(Math.ceil(size * 2), Math.ceil(size * 2))
    smooth: true
    mipmap: true
    source: "image://icon/" + name + "/" + String(color).slice(1, 7) + "/" + stroke
}
