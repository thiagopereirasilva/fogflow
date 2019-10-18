# Program to capture the motion of an object from camera/video_file and send it to FogFlow Operator
# indicating its box and direction. All parameters must be informed in camera_motion.json

import time
import threading
import signal
import sys
import json
import requests
import logging
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from os import path
# CameraMotion class
from imutils import resize
from imutils.video import VideoStream
import cv2
from collections import deque
import numpy as np
from datetime import datetime


# Global variables
discoveryURL = 'http://10.7.40.146/ngsi9'
brokerURL = ''
profile = {}
runThread = True


class CameraMotion:

    def __init__(self, camera_id, src_video=0, max_width=500, roi=None, min_area=500, crossline=1):
        # identification of the camera
        self.camera_id = camera_id
        # video source (file_name, rtsp_url, or 0:/dev/video0)
        self.video_stream = VideoStream(src=src_video)
        # set the maximum width of the frame
        self.max_width = max_width
        # region of interest: 'startCol,startLin,endCol,endLin'
        self.roi = roi
        if roi is not None:
            (startCol, startLin, endCol, endLin) = roi.split(',')
            self.startCol = int(startCol)
            self.startLin = int(startLin)
            self.endCol = int(endCol)
            self.endLin = int(endLin)

        self.min_area = min_area  # consider only objects with this minimum area size
        self.crossline = crossline  # shape of the cross line to detect motion: 1(-) 2(|) 3(/) 4(\)

    # check if two line segments have an intersection
    def segment_intersection(self, line1, line2):
        class Point:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        def ccw(A, B, C):
            return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)

        def intersect(A, B, C, D):
            return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

        x1 = Point(line1[0][0], line1[0][1])
        y1 = Point(line1[1][0], line1[1][1])
        x2 = Point(line2[0][0], line2[0][1])
        y2 = Point(line2[1][0], line2[1][1])
        return intersect(x1, y1, x2, y2)

    # gets the centroid of the box
    def centroid(self, pts):
        coordxcentroid = (pts[0] + pts[0] + pts[2]) // 2
        coordycentroid = (pts[1] + pts[1] + pts[3]) // 2
        return (coordxcentroid, coordycentroid)

    def run(self):
        global runThread
        firstFrame = None

        # initialize the frame dimensions (we'll set them as soon as we read
        # the first frame from the video)
        W = None
        H = None

        # initialize the list of tracked box
        # and the coordinate deltas
        from collections import deque
        box = deque(maxlen=2)
        (dX, dY) = (0, 0)
        direction = ""

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

            # if the frame dimensions are empty, set them
            if W is None or H is None:
                (H, W) = frame.shape[:2]
                if self.crossline == 1:  # horizontal
                    crossline = ((0, H // 2), (W, H // 2))
                elif self.crossline == 2:  # vertical
                    crossline = ((W // 2, 0), (W // 2, H))
                elif self.crossline == 3:  # diagonal /
                    crossline = ((0, H), (W, 0))
                elif self.crossline == 4:  # diagonal \
                    crossline = ((0, 0), (W, H))
                else:
                    logging.info("[ERROR] invalid cross line parameter")
                    break

            # convert the frame to grayscale, and blur it
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            # if the first frame is None, initialize it
            if firstFrame is None:
                logging.info("[INFO] starting background model...")
                firstFrame = gray.copy().astype("float")
                continue

            # accumulate the weighted average between the current frame and
            # previous frames, then compute the difference between the current
            # frame and running average
            cv2.accumulateWeighted(src=gray, dst=firstFrame, alpha=0.5)
            frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(firstFrame))
            thresh = cv2.threshold(frameDelta, 5, 255, cv2.THRESH_BINARY)[1]

            # dilate the thresholded image to fill in holes, then find contours
            # on thresholded image
            thresh = cv2.dilate(thresh, None, iterations=2)
            (_, cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # only proceed if at least one contour was found
            if len(cnts) > 0:
                # find the largest contour in the mask
                c = max(cnts, key=cv2.contourArea)

                # if the contour is too small, ignore it
                if cv2.contourArea(c) >= self.min_area:
                    # compute the bounding box for the contour
                    (x, y, w, h) = cv2.boundingRect(c)
                    box.appendleft((x, y, w, h))
                else:
                    box.clear()
            else:
                box.clear()

            # track the last two points
            if len(box) > 1:
                # compute the centroid line of the moving object
                objline = (self.centroid(box[0]), self.centroid(box[1]))
                # check if the object is crossing the crossline
                if self.segment_intersection(crossline, objline):
                    dX = self.centroid(box[0])[0] - self.centroid(box[1])[0]
                    dY = self.centroid(box[0])[1] - self.centroid(box[1])[1]
                    (dirX, dirY) = ("", "")

                    # ensure there is significant movement in the
                    # x-direction or y-direction
                    if np.abs(dX) > 4:
                        dirX = "Right" if np.sign(dX) == 1 else "Left"
                    if np.abs(dY) > 4:
                        dirY = "Down" if np.sign(dY) == 1 else "Up"

                    # handle when both directions are non-empty
                    if dirX != "" and dirY != "":
                        direction = "{}-{}".format(dirY, dirX)
                    # otherwise, only one direction is non-empty
                    else:
                        direction = dirX if dirX != "" else dirY

                    (x, y, w, h) = box[0]
                    timestamp = datetime.now()
                    filename = timestamp.strftime(self.camera_id + '_%Y-%m-%d_%H-%M-%S-%f.jpg')
                    logging.info("[INFO] captured object: {}".format(filename))
                    objects = {'box': [[x, y], [x + w, y + h]], 'direction': direction}
                    with open(filename.replace('jpg', 'json'), 'w') as write_file:
                        json.dump(objects, write_file)
                    cv2.imwrite(filename, frame)
                    publishMySelf(filename, timestamp.strftime('%Y-%m-%d_%H-%M-%S-%f'), objects)

        # cleanup the camera
        logging.info('[INFO] closing video source')
        self.video_stream.stop()

##########################################
# FogFlow/Main code:
def signal_handler(signal, frame):
    global runThread
    logging.info('[WARN] Signal to stop this process!')
    # stop the thread running
    runThread = False
    # delete my registration and context entity
    unpublishMySelf()
    sys.exit(0)


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


def publishMySelf(filename, timestamp, objects):
    global profile, brokerURL

    # device entity
    deviceCtxObj = {}
    deviceCtxObj['entityId'] = {}
    deviceCtxObj['entityId']['id'] = 'Device.' + profile['type'] + '.' + profile['id']
    deviceCtxObj['entityId']['type'] = profile['type']
    deviceCtxObj['entityId']['isPattern'] = False

    deviceCtxObj['attributes'] = {}
    deviceCtxObj['attributes']['url'] = {'type': 'string',
                                         'value': 'http://' + profile['myIP'] + ':' + str(profile['myPort']) + '/' + filename}
    deviceCtxObj['attributes']['timestamp'] = {'type': 'string',
                                         'value': timestamp}
    deviceCtxObj['attributes']['object'] = {'type':'object',
                                             'value': objects}
    deviceCtxObj['attributes']['iconURL'] = {'type': 'string', 'value': profile['iconURL']}

    deviceCtxObj['metadata'] = {}
    deviceCtxObj['metadata']['location'] = {'type': 'point', 'value': {'latitude': profile['location']['latitude'],
                                                                       'longitude': profile['location']['longitude']}}
    deviceCtxObj['metadata']['cameraID'] = {'type': 'string', 'value': profile['id']}

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


class RequestHandler(BaseHTTPRequestHandler):
    # handle GET command
    def do_GET(self):
        if self.path != '/':
            # send code 200 response
            filename = self.path[1:]
            if path.exists(filename):
                self.send_response(200)
                ctype = 'image/jpg' if '.jpg' in filename else 'application/json'
                # send header first
                self.send_header('Content-type', ctype)
                self.end_headers()

                # send the image file content to client
                self.wfile.write(loadFile(filename))
                return
            
        self.send_error(404, 'File not Found')
        return


def thread_function(name):
    global runThread, profile
    logging.info("[INFO] Thread %s: starting", name)

    camera = CameraMotion(camera_id=profile['id'], src_video=profile['source'], roi=profile['roi'], 
        min_area=profile['area'], crossline=profile['crossline'])
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
                 + str(profile['myPort']) + '/<filename>')
    signal.signal(signal.SIGINT, signal_handler)
    server_address = ('0.0.0.0', profile['myPort'])
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever() # blocking function call


if __name__ == '__main__':
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    cfgFileName = 'camera_motion.json'
    if len(sys.argv) >= 2:
        cfgFileName = sys.argv[1]

    try:
        with open(cfgFileName) as json_file:
            profile = json.load(json_file)
    except Exception as error:
        logging.info('[ERROR] failed to load the device profile')
        sys.exit(0)

    run()
