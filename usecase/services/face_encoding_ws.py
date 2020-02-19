from flask import Flask, request
import face_recognition
import cv2
from urllib.request import urlopen
from urllib.parse import urlparse
import numpy as np
import json

app = Flask(__name__)

def url2Image(url):
    with urlopen(url) as response:
        data = response.read()

    image = np.asarray(bytearray(data), dtype=np.uint8)
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    return image


@app.route('/api/', methods=['POST'])
def api():
    input_data = request.get_json()
    if 'image' in input_data.keys():
        print("[INFO] image to process: {}".format(input_data['image']))
    else:
        return '[ERROR] image attribute not informed!', 404
    if 'faces' not in input_data.keys():
        return '[ERROR] no face to encode!', 404
    
    boxes = input_data['faces']['boxes']
    
    if len(boxes) > 0:
        print("[INFO] {} face(s) to encode".format(len(boxes)))
    else:
        return '[ERROR] no face to encode!', 404

    urlprs = urlparse(input_data['image'])
    if urlprs.scheme == 'file':
        frame = cv2.imread(urlprs.path)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    if urlprs.scheme == 'http' or urlprs.scheme == 'https':
        rgb = url2Image(input_data['image'])

    if rgb is None:
        return '[ERROR] image file ({}) not found!'.format(input_data['image']), 404

    # convert boxes[left-0, top-1, right-2, bottom-3] to boxes[(top, right, bottom, left)]
    fr_boxes = []
    for box in boxes:
        fr_boxes.append((box[1], box[2], box[3], box[0]))

    encodings = face_recognition.face_encodings(rgb, fr_boxes)
    
    faces = []
    for (box, encoding) in zip(boxes, encodings):
        arr = np.array(encoding, dtype=np.float32)
        faces.append({'box': box, 'encodings': arr.tolist()})

    output_data = {}
    output_data['image'] = input_data['image']
    output_data['faces'] = faces

    return json.dumps(output_data)

if __name__ == '__main__':

    app.run(debug=True, host='0.0.0.0')



