#!/usr/bin/env python
import time
import os
import threading
import numpy as np
import signal
import sys
import json
import requests
import logging


discoveryURL = 'http://10.7.40.146/ngsi9'
brokerURL = ''
profile = {}
runThread = True

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

def signal_handler(signal, frame):
    global runThread
    logging.info('[WARN] Signal to stop! unpublishing my url')
    # stop the thread running
    runThread = False
    # delete my registration and context entity
    unpublishMySelf()
    sys.exit(0)


def loadImage(file):
    try:
        with open(file, 'rb') as file:
            return file.read()   
    except Exception as error:
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
    discoveryReq['restriction'] = {'scopes':[{'scopeType': 'nearby', 'scopeValue': nearby}]}
    
    discoveryURL = profile['discoveryURL']
    headers = {'Accept' : 'application/json', 'Content-Type' : 'application/json'}
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
    
def publishMySelf():
    global profile, brokerURL
    
    # device entity
    deviceCtxObj = {}
    deviceCtxObj['entityId'] = {}
    deviceCtxObj['entityId']['id'] = 'Device.' + profile['type'] + '.' + profile['id']
    deviceCtxObj['entityId']['type'] = profile['type']        
    deviceCtxObj['entityId']['isPattern'] = False
    
    deviceCtxObj['attributes'] = {}
    deviceCtxObj['attributes']['url'] = {'type': 'string', 'value': 'http://' + profile['myIP'] + ':' + str(profile['myPort']) + '/image'}
    deviceCtxObj['attributes']['iconURL'] = {'type': 'string', 'value': profile['iconURL']}    
    
    deviceCtxObj['metadata'] = {}
    deviceCtxObj['metadata']['location'] = {'type': 'point', 'value': {'latitude': profile['location']['latitude'], 'longitude': profile['location']['longitude'] }}
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

def updateContext(broker, ctxObj):        
    ctxElement = object2Element(ctxObj)
    
    updateCtxReq = {}
    updateCtxReq['updateAction'] = 'UPDATE'
    updateCtxReq['contextElements'] = []
    updateCtxReq['contextElements'].append(ctxElement)

    headers = {'Accept' : 'application/json', 'Content-Type' : 'application/json'}
    response = requests.post(broker + '/updateContext', data=json.dumps(updateCtxReq), headers=headers)
    if response.status_code != 200:
        logging.info('[ERROR] failed to UPDATE context: ' + response.text)


def deleteContext(broker, ctxObj):        
    ctxElement = object2Element(ctxObj)
    
    updateCtxReq = {}
    updateCtxReq['updateAction'] = 'DELETE'
    updateCtxReq['contextElements'] = []
    updateCtxReq['contextElements'].append(ctxElement)

    headers = {'Accept' : 'application/json', 'Content-Type' : 'application/json'}
    response = requests.post(broker + '/updateContext', data=json.dumps(updateCtxReq), headers=headers)
    if response.status_code != 200:
        logging.info('[ERROR] failed to DELETE context: ' + response.text)


class RequestHandler(BaseHTTPRequestHandler):  
  #handle GET command
  def do_GET(self):
    try:
      if self.path == '/image':

        #send code 200 response
        self.send_response(200)

        #send header first
        self.send_header('Content-type','image/png')
        self.end_headers() 
        
        #send the image file content to client
        self.wfile.write(loadImage('content.jpg'))
        return
      
    except IOError:
      self.send_error(404, 'error to fetch images from the camera')
      return
  
def thread_function(name):
    global runThread
    
    logging.info("[INFO] Thread %s: starting", name)
    while runThread:
        logging.info('[INFO] publishing my url')
        #publishMySelf()
        time.sleep(3)
    
    logging.info("[INFO] Thread %s: finishing", name)


def run():
    global brokerURL
    brokerURL = findNearbyBroker()
    if brokerURL == '':
        logging.info('[ERROR] failed to find a nearby broker')
        sys.exit(0)
        
    #announce myself        
    publishMySelf()
    
    thread = threading.Thread(target=thread_function, args=(1,))
    thread.start()

    logging.info('[INFO] local image server at http://' + profile['myIP'] + ':' 
                + str(profile['myPort']) + '/image')  
    signal.signal(signal.SIGINT, signal_handler)  
    server_address = ('0.0.0.0', profile['myPort'])
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever()
  
  
if __name__ == '__main__':
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%H:%M:%S")

    cfgFileName = 'profile.json' 
    if len(sys.argv) >= 2:
        cfgFileName = sys.argv[1]
    
    try:       
        with open(cfgFileName) as json_file:
            profile = json.load(json_file)
    except Exception as error:
        logging.info('[ERROR] failed to load the device profile')
        sys.exit(0)

    run()

