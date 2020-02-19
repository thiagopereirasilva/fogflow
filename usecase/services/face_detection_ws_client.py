# Usage:
# python3 face_detection_ws_client.py -ho http://localhost:5000/api/ -i file:///home/pi/openvino_samples/faces-example.jpg

import cv2
from urllib.request import urlopen
from urllib.parse import urlparse
import numpy as np
import argparse
import requests
import json

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--image", required=True, help="image url {file:///path | http(s)://host/path} of input image")
ap.add_argument("-ho", "--host", required=True, help="host url to process image")
args = vars(ap.parse_args())


def url2Image(url):
    with urlopen(url) as response:
        data = response.read()

    image = np.asarray(bytearray(data), dtype=np.uint8)
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    return image


# prepare image to read and show detected faces
frame = None
urlprs = urlparse(args['image'])
if urlprs.scheme == 'file':
    frame = cv2.imread(urlprs.path)
if urlprs.scheme == 'http' or urlprs.scheme == 'https':
    frame = url2Image(args['image'])

if frame is None:
    print('[ERROR] image file ({}) not found!'.format(args['image']))
    exit(1)

# request the face detection to the web server
j_data = '{"image": "' + args['image'] + '"}'
headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
response = requests.post(args['host'], data=j_data, headers=headers)
if response.status_code is not 200:
   print('[ERROR] host returned code {}'.format(response.status_code))
   exit(1)

data = response.json()
boxes = data['faces']['boxes']

# Draw detected faces on the frame.
for box in boxes:
    cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), color=(0, 255, 0))

# Show resulsts
cv2.imshow('Image processed', frame)
cv2.waitKey(0)
cv2.destroyAllWindows()
