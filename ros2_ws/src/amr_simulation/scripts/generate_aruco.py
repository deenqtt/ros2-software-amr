#!/usr/bin/env python3
"""Generate ArUco marker ID=0 (4x4_50 dict) as PNG for Gazebo texture."""
import sys
import os
import cv2
import numpy as np

OUTPUT = os.path.join(
    os.path.dirname(__file__),
    '../models/aruco_dock/materials/textures/aruco_0.png'
)

def main():
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    size = 400  # pixels — big enough for clear texture
    img = np.zeros((size, size), dtype=np.uint8)
    cv2.aruco.drawMarker(aruco_dict, 0, size, img, 1)
    # Add white border (10% margin each side)
    border = size // 10
    canvas = np.ones((size + 2 * border, size + 2 * border), dtype=np.uint8) * 255
    canvas[border:border + size, border:border + size] = img
    out = os.path.abspath(OUTPUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, canvas)
    print(f'ArUco marker written → {out}')

if __name__ == '__main__':
    main()
