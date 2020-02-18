# Program to capture the motion of an object from camera/video_file and send it to FogFlow Operator
# indicating its box and direction. All parameters must be informed in camera_motion_people.json

import threading
import signal
import sys
import json
import urllib
import requests
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from os import path
# CameraMotion class
from edgetpu.detection.engine import DetectionEngine
from imutils import resize
from imutils.video import VideoStream
import cv2
from datetime import datetime
from PIL import Image

# Global variables
discoveryURL = ''
brokerURL = ''
profile = {}
runThread = True


#  CameraMotion main code
class CameraMotion:

    def __init__(self, model, labels, confidence, camera_id, direction, src_video, roi=None, max_width=500):
        # loading the deep learning model
        self.model = DetectionEngine(model)
        self.labels = labels
        self.confidence = confidence
        # identification of the camera
        self.camera_id = camera_id
        # video source (file_name, rtsp_url, or 0:/dev/video0)
        self.video_stream = VideoStream(src=src_video)
        # region of interest: 'startCol,startLin,endCol,endLin'
        self.roi = roi
        if roi is not None:
            (startCol, startLin, endCol, endLin) = roi.split(',')
            self.startCol = int(startCol)
            self.startLin = int(startLin)
            self.endCol = int(endCol)
            self.endLin = int(endLin)
        self.max_width = max_width
        self.direction = direction

    def run(self):
        global runThread

        self.video_stream.start()
        # loop over the frames of the video
        while runThread:
            frame = self.video_stream.read()
            if frame is None:
                break

            # crop ROI (region of interest) from image if required
            if self.roi is not None:
                frame = frame[self.startLin:self.endLin, self.startCol:self.endCol]

            # resize the frame
            frame = resize(frame, width=self.max_width)
            orig = frame.copy()

            # prepare the frame for object detection by converting (1) it
            # from BGR to RGB channel ordering and then (2) from a NumPy
            # array to PIL image format
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = Image.fromarray(frame)

            # make predictions on the input frame
            results = self.model.DetectWithImage(frame, threshold=self.confidence,
                                                 keep_aspect_ratio=True, relative_coord=False)

            # check if object was detected
            if len(results) > 0:
                boxes = []
                for r in results:
                    # extract the bounding box and box and predicted class label
                    box = r.bounding_box.flatten().astype("int")
                    (startX, startY, endX, endY) = box
                    boxes.append([int(startX), int(startY), int(endX), int(endY)])
                timestamp = datetime.now()
                filename = timestamp.strftime(self.camera_id + '_%Y-%m-%d_%H-%M-%S_%f_' + self.direction + '.jpg')
                logging.info("[INFO] captured object: {}".format(filename))
                cv2.imwrite('images/' + filename, orig)
                publishMySelf(filename, self.direction, boxes)

        # cleanup the camera
        logging.info('[INFO] closing video source')
        self.video_stream.stop()


##########################################
# FogFlow/Main code:

def getTimestamp(url):
    # resp = urllib.request.urlopen("http://localhost:5000/timestamp")
    with urllib.request.urlopen(url) as resp:
        data = resp.info()
    return str(data['timestamp'])


def loadFile(filename):
    try:
        with open(filename, 'rb') as file:
            return file.read()
    except Exception as e:
        logging.info('[ERROR] failed to load file ' + filename)
        return ''


def findNearbyBroker():
    global profile, discoveryURL

    nearby = {}
    nearby['latitude'] = profile['location']['latitude']
    nearby['longitude'] = profile['location']['longitude']
    nearby['limit'] = 1

    discoveryReq = {}
    discoveryReq['entities'] = [{'type': 'IoTBroker', 'isPattern': True}]
    discoveryReq['restriction'] = {'scopes': [{'scopeType': 'nearby', 'scopeValue': nearby}]}

    discoveryURL = profile['discoveryURL']
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    response = requests.post(discoveryURL + '/discoverContextAvailability', data=json.dumps(discoveryReq),
                             headers=headers)
    if response.status_code != 200:
        logging.info('[ERROR] failed to find a nearby IoT Broker')
        return ''

    logging.info('[INFO] registration successed, json response: ' + response.text)
    registrations = json.loads(response.text)

    for registration in registrations['contextRegistrationResponses']:
        providerURL = registration['contextRegistration']['providingApplication']
        if providerURL != '':
            return providerURL

    return ''


def publishMySelf(filename, direction, boxes):
    global profile, brokerURL

    faces = []
    for box in boxes:
        faces.append({'box': box})

    # device entity
    deviceCtxObj = {}
    deviceCtxObj['entityId'] = {}
    deviceCtxObj['entityId']['id'] = 'Device.' + profile['type'] + '.' + profile['id']
    deviceCtxObj['entityId']['type'] = profile['type']
    deviceCtxObj['entityId']['isPattern'] = False

    deviceCtxObj['attributes'] = {}
    deviceCtxObj['attributes']['image_url'] = {'type': 'string', 'value': 'http://' + profile['myIP'] +
                                                ':' + str(profile['myPort']) + '/image/' + filename}
    deviceCtxObj['attributes']['direction'] = {'type': 'string', 'value': direction}
    deviceCtxObj['attributes']['faces'] = {'type': 'array', 'value': faces}
    deviceCtxObj['attributes']['iconURL'] = {'type': 'string', 'value': profile['iconURL']}
    deviceCtxObj['attributes']['camera_id'] = {'type': 'string', 'value': profile['id']}
    deviceCtxObj['attributes']['timestamp_facesDetection'] = {'type': 'string',
                                                               'value': getTimestamp(profile['timestamp_server'])}
    deviceCtxObj['attributes']['faceencoding_server'] = {'type': 'string', 'value': profile['faceencoding_server']}
    deviceCtxObj['attributes']['database'] = {'type': 'string', 'value': profile['database']}
    deviceCtxObj['attributes']['timestamp_server'] = {'type': 'string', 'value': profile['timestamp_server']}
    deviceCtxObj['metadata'] = {}
    deviceCtxObj['metadata']['location'] = {'type': 'point', 'value': {'latitude': profile['location']['latitude'],
                                                                       'longitude': profile['location']['longitude']}}
    updateContext(brokerURL, deviceCtxObj)


def unpublishMySelf():
    global profile, brokerURL

    # device entity
    deviceCtxObj = {}
    deviceCtxObj['entityId'] = {}
    deviceCtxObj['entityId']['id'] = 'Device.' + profile['type'] + '.' + profile['id']
    deviceCtxObj['entityId']['type'] = profile['type']
    deviceCtxObj['entityId']['isPattern'] = False

    deleteContext(brokerURL, deviceCtxObj)


def object2Element(ctxObj):
    ctxElement = {}

    ctxElement['entityId'] = ctxObj['entityId']

    ctxElement['attributes'] = []
    if 'attributes' in ctxObj:
        for key in ctxObj['attributes']:
            attr = ctxObj['attributes'][key]
            ctxElement['attributes'].append({'name': key, 'type': attr['type'], 'value': attr['value']})

    ctxElement['domainMetadata'] = []
    if 'metadata' in ctxObj:
        for key in ctxObj['metadata']:
            meta = ctxObj['metadata'][key]
            ctxElement['domainMetadata'].append({'name': key, 'type': meta['type'], 'value': meta['value']})

    return ctxElement


def updateContext(broker, ctxObj):
    ctxElement = object2Element(ctxObj)

    updateCtxReq = {}
    updateCtxReq['updateAction'] = 'UPDATE'
    updateCtxReq['contextElements'] = []
    updateCtxReq['contextElements'].append(ctxElement)

    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    response = requests.post(broker + '/updateContext', data=json.dumps(updateCtxReq), headers=headers)
    if response.status_code != 200:
        logging.info('[ERROR] failed to UPDATE context: ' + response.text)


def deleteContext(broker, ctxObj):
    ctxElement = object2Element(ctxObj)

    updateCtxReq = {}
    updateCtxReq['updateAction'] = 'DELETE'
    updateCtxReq['contextElements'] = []
    updateCtxReq['contextElements'].append(ctxElement)

    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    response = requests.post(broker + '/updateContext', data=json.dumps(updateCtxReq), headers=headers)
    if response.status_code != 200:
        logging.info('[ERROR] failed to DELETE context: ' + response.text)


######
# HTTP server code
class RequestHandler(BaseHTTPRequestHandler):
    # handle GET command
    def do_GET(self):
        if self.path == '/timestamp':
            self.send_response(200)
            self.send_header
            self.send_header('timestamp', str(datetime.now()))
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f").encode('utf-8'))
            return
        elif self.path[:7] == '/image/':
            # get image file name
            filename = 'images/' + self.path[7:]
            if path.exists(filename):
                self.send_response(200)
                conttype = 'image/jpg' if '.jpg' in filename else 'application/json'
                # send header first
                self.send_header('Content-type', conttype)
                self.end_headers()
                # send the image file content to client
                self.wfile.write(loadFile(filename))
                return
        else:
            self.send_error(404, 'File not Found')
            return


##############
# Main functions
def signal_handler(signal, frame):
    global runThread
    logging.info('[WARN] Signal to stop this process!')
    # stop the thread running
    runThread = False
    # delete my registration and context entity
    #logging.info('[EXIT] Unpublishing myself and exiting.')
    #unpublishMySelf()
    sys.exit(0)


def thread_function(name):
    global runThread, profile
    logging.info("[INFO] Thread %s: starting", name)

    camera = CameraMotion(camera_id=profile['id'], src_video=profile['source'], roi=profile['roi'],
                          max_width=profile['max_width'], direction=profile['direction'],
                          model=profile['model'], labels=profile['labels'], confidence=profile['confidence'])
    camera.run()

    logging.info("[INFO] Thread %s: finishing", name)


def run():
    global brokerURL
    brokerURL = findNearbyBroker()
    if brokerURL == '':
        logging.info('[ERROR] failed to find a nearby broker')
        sys.exit(0)

    thread = threading.Thread(target=thread_function, args=(1,))
    thread.start()

    logging.info('[INFO] local image server at http://' + profile['myIP'] + ':'
                 + str(profile['myPort']) + '/image/<filename>')

    signal.signal(signal.SIGINT, signal_handler)
    server_address = ('0.0.0.0', profile['myPort'])
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever()  # blocking function call


if __name__ == '__main__':
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    cfgFileName = 'camera_motion_faces.json'
    if len(sys.argv) >= 2:
        cfgFileName = sys.argv[1]

    try:
        with open(cfgFileName) as json_file:
            profile = json.load(json_file)
    except Exception as error:
        logging.info('[ERROR] failed to load the device profile')
        sys.exit(0)

    run()
