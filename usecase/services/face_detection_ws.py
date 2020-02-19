from flask import Flask, request, redirect, url_for, flash, jsonify
import json
import cv2
from urllib.request import urlopen
from urllib.parse import urlparse
import numpy as np

app = Flask(__name__)

def url2Image(url):
    with urlopen(url) as response:
        data = response.read()

    image = np.asarray(bytearray(data), dtype=np.uint8)
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    return image


@app.route('/api/', methods=['POST'])
def api():
    data = request.get_json()
    if 'image' in data.keys():
        print("[INFO] image to process: {}".format(data['image']))
    else:
        return '[ERROR] image attribute not informed!', 404

    urlprs = urlparse(data['image'])
    if urlprs.scheme == 'file':
        frame = cv2.imread(urlprs.path)
    if urlprs.scheme == 'http' or urlprs.scheme == 'https':
        frame = url2Image(data['image'])

    if frame is None:
        return '[ERROR] image file ({}) not found!'.format(data['image']), 404

    # Prepare input blob and perform an inference.
    blob = cv2.dnn.blobFromImage(frame, size=(672, 384), ddepth=cv2.CV_8U)
    net.setInput(blob)

    detections = net.forward()

    boxes = []
    for detection in detections.reshape(-1, 7):
        confidence = float(detection[2])
        if confidence > 0.5:
            xmin = int(detection[3] * frame.shape[1])
            ymin = int(detection[4] * frame.shape[0])
            xmax = int(detection[5] * frame.shape[1])
            ymax = int(detection[6] * frame.shape[0])
            boxes.append([xmin, ymin, xmax, ymax])
    data['faces'] = {'boxes': boxes}

    return jsonify(data)

if __name__ == '__main__':
    # Load the model.
    print("[INFO] Loading the model")
    net = cv2.dnn.readNet('face-detection-adas-0001.xml', 'face-detection-adas-0001.bin')

    # Specify target device.
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_MYRIAD)

    app.run(debug=False, host='0.0.0.0')



