from flask import Flask, jsonify, abort, request, make_response
import requests 
import json
import threading
import os
import urllib

# import the necessary packages
import cv2
import numpy as np

# initialize the list of class labels MobileNet SSD was trained to
# detect, then generate a set of bounding box colors for each class
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
           "sofa", "train", "tvmonitor"]
net = cv2.dnn.readNetFromCaffe("MobileNetSSD_deploy.prototxt.txt", "MobileNetSSD_deploy.caffemodel")

# HTTP server
app = Flask(__name__, static_url_path = "")

# global variables
brokerURL = ''
outputs = []
timer = None
lock = threading.Lock()

@app.errorhandler(400)
def not_found(error):
    return make_response(jsonify( { 'error': 'Bad request' } ), 400)

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify( { 'error': 'Not found' } ), 404)

@app.route('/admin', methods=['POST'])
def admin():    
    if not request.json:
        abort(400)
    
    configObjs = request.json
    handleConfig(configObjs)    
        
    return jsonify({ 'responseCode': 200 })


@app.route('/notifyContext', methods = ['POST'])
def notifyContext():
    lock.acquire()
    print("=============notify=============")

    if not request.json:
        abort(400)
    	
    objs = readContextElements(request.json)    
    #print(objs)

    handleNotify(objs)
    lock.release()
    return jsonify({ 'responseCode': 200 })


def element2Object(element):
    ctxObj = {}
    
    ctxObj['entityId'] = element['entityId'];
    
    ctxObj['attributes'] = {}  
    if 'attributes' in element:
        for attr in element['attributes']:
            ctxObj['attributes'][attr['name']] = {'type': attr['type'], 'value': attr['value']}   
    
    ctxObj['metadata'] = {}
    if 'domainMetadata' in element:    
        for meta in element['domainMetadata']:
            ctxObj['metadata'][meta['name']] = {'type': meta['type'], 'value': meta['value']}
    
    return ctxObj

def object2Element(ctxObj):
    ctxElement = {}
    
    ctxElement['entityId'] = ctxObj['entityId'];
    
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

def readContextElements(data):
    #print(data)

    ctxObjects = []
    
    for response in data['contextResponses']:
        if response['statusCode']['code'] == 200:
            ctxObj = element2Object(response['contextElement'])
            ctxObjects.append(ctxObj)
    
    return ctxObjects

def handleNotify(contextObjs):
    #print("TODO O OBJETO")
    #print(json.dumps(contextObjs, indent=3))

    for ctxObj in contextObjs:
        #if(ctxObj['entityId']):
        processInputStreamData(ctxObj)

def processInputStreamData(obj):
    print('===============receive context entity====================')
    print(json.dumps(obj, indent=3))
    #print(obj)

    url = obj["attributes"]["url"]["value"]
    # run the object detector neural network
    print('===============retrieve image from====================')
    print(url)
    image = url2Image(url)
    (h, w) = image.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()
    #confidence = detections[0, 0, 0, 2]
    idx = int(detections[0, 0, 0, 1])
    #box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
    #(startX, startY, endX, endY) = box.astype("int")
    # display the prediction
    objclass = CLASSES[idx]

    # publish the counting result
    entity = {}       
    entity['id'] = "Stream.VehicleType." + obj["entityId"]["id"].split('.')[-1]
    entity['type'] = "VehicleType"
    entity['url'] = url
    entity['timestamp'] = obj["attributes"]["timestamp"]["value"]
    entity['direction'] = obj["attributes"]["direction"]["value"]
    entity['class'] = objclass
    metadata = obj["metadata"]
    publishResult(entity, metadata)


def url2Image(url): 
    resp = urllib.urlopen(url)
    data = resp.read()
    
    image = np.asarray(bytearray(data), dtype=np.uint8)    
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    rgbImg = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)    
    return rgbImg



def handleConfig(configurations):  
    global brokerURL
    global num_of_outputs  
    for config in configurations:        
        if config['command'] == 'CONNECT_BROKER':
            brokerURL = config['brokerURL']
        if config['command'] == 'SET_OUTPUTS':
            outputs.append({'id': config['id'], 'type': config['type']})
    

def publishResult(result, metadata):
    resultCtxObj = {}
        
    resultCtxObj['entityId'] = {}
    resultCtxObj['entityId']['id'] = result['id']
    resultCtxObj['entityId']['type'] = result['type']
    resultCtxObj['entityId']['isPattern'] = False    
    
    resultCtxObj['attributes'] = {}
    resultCtxObj['attributes']['class'] = {'type': 'string', 'value': result['class']}
    resultCtxObj['attributes']['url'] = {'type': 'string', 'value': result['url']}
    resultCtxObj['attributes']['timestamp'] = {'type': 'string', 'value': result['timestamp']}
    resultCtxObj['attributes']['direction'] = {'type': 'string', 'value': result['direction']}

    resultCtxObj['metadata'] = metadata

    # publish the real time results as context updates    
    updateContext(resultCtxObj)

def updateContext(ctxObj):
    print('===============update context entity====================')
    print(json.dumps(ctxObj, indent=3))
    global brokerURL
    if brokerURL == '':
        return
        
    ctxElement = object2Element(ctxObj)
    
    updateCtxReq = {}
    updateCtxReq['updateAction'] = 'UPDATE'
    updateCtxReq['contextElements'] = []
    updateCtxReq['contextElements'].append(ctxElement)

    headers = {'Accept' : 'application/json', 'Content-Type' : 'application/json'}
    response = requests.post(brokerURL + '/updateContext', data=json.dumps(updateCtxReq), headers=headers)
    if response.status_code != 200:
        print('failed to update context')
        print(response.text)

                             
if __name__ == '__main__':
    myport = int(os.environ['myport'])
    
    myCfg = os.environ['adminCfg']
    adminCfg = json.loads(myCfg)
    handleConfig(adminCfg)
    
    app.run(host='0.0.0.0', port=myport)
    
    #timer.cancel()
