#!/usr/bin/env python

import asyncio
import json
import logging
import websockets
import RPi.GPIO as GPIO
import Adafruit_DHT
import w1thermsensor
import time

USERS = set()
VALUE = 0

def break_beam_callback(channel):
  if GPIO.input(BEAM_PIN):
    print("beam unbroken")
  else:
    print("beam broken")

def magnetic_sensor_callback(pin):
  global magnetic_sensors
  current_state = GPIO.input(pin)
  if current_state != magnetic_sensors[pin]["state"]:
    magnetic_sensors[pin]["state"] = current_state
    websockets.broadcast(USERS, magnetic_sensor_event(magnetic_sensors[pin]["name"], current_state))

DOOR_SENSOR_PIN = 24
WINDOW_R_SENSOR_PIN = 17
WINDOW_L_SENSOR_PIN = 27

magnetic_sensors = {
  DOOR_SENSOR_PIN: {
    "name": "door",
    "state": 0,
  },
  WINDOW_R_SENSOR_PIN: {
    "name": "windowRight",
    "state": 0,
  },
  WINDOW_L_SENSOR_PIN: {
    "name": "windowLeft",
    "state": 0,
  }
}

humidity = 0
temperature = 0
temperatureOutside = 0

BEAM_PIN = 27
GPIO.setmode(GPIO.BCM)

for pin in magnetic_sensors:
  GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
  GPIO.add_event_detect(pin, GPIO.BOTH, callback=magnetic_sensor_callback)
  magnetic_sensors[pin]["state"] = GPIO.input(pin)

# GPIO.setup(BEAM_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
# GPIO.add_event_detect(BEAM_PIN, GPIO.BOTH, callback=break_beam_callback)

sensor = w1thermsensor.W1ThermSensor()

def users_event():
  return json.dumps({"type": "users", "count": len(USERS)})

def value_event():
  return json.dumps({"type": "value", "value": VALUE})

def magnetic_sensor_event(event, value):
  return json.dumps({
    "type": "sensor",
    "target": event,
    "value": value,
    "timestamp": time.time(),
  })

def beam_break_event(sensor_value):
  return json.dumps({"type": "beam_break", "target": "room1_doors"})

def temp_and_humidity_value(temp, humidity, tempOutside):
  return json.dumps({"type": "sensor", "target": "DHT11", "value": {
    "temperature": temp,
    "humidity": humidity,
    "temperatureOutside": tempOutside,
    "timestamp": time.time(),
  }})

def full_info():
  global temperature, humidity, temperatureOutside

  return json.dumps({
    "type": "fullData",
    "weather": {
      "temperature": temperature,
      "humidity": humidity,
      "temperatureOutside": temperatureOutside,
    },
    "sensors": {
      "door": GPIO.input(DOOR_SENSOR_PIN),
      "windowRight": GPIO.input(WINDOW_R_SENSOR_PIN),
      "windowLeft": GPIO.input(WINDOW_L_SENSOR_PIN),
    },
    "timestamp": time.time(),
  })

async def counter(websocket):
  global USERS
  try:
    USERS.add(websocket)
    # print("User connected")
    websockets.broadcast(USERS, users_event())

    await websocket.send(full_info())

    async for message in websocket:
      event = json.loads(message)
      if event["action"] == "minus":
        websockets.broadcast(USERS, value_event())
      else:
        logging.error("unsupported event: %s", event)
  finally:
    print("User disconnected")
    USERS.remove(websocket)
    websockets.broadcast(USERS, users_event())

async def watchSensors():
  global temperature, humidity, temperatureOutside
  while True:
    humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, 12)
    # print("Read DHT11", humidity, temperature)
    temperatureOutside = sensor.get_temperature()
    # print("Temperature", temperatureOutside)
    websockets.broadcast(USERS, temp_and_humidity_value(temperature, humidity, temperatureOutside))
    await asyncio.sleep(60)
    

async def main():
  async with websockets.serve(counter, "localhost", 6789):
    await watchSensors()
    await asyncio.Future()  # run forever

if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print('Interrupted')
    GPIO.cleanup()
  except:
    print('Interrupted (other)')
    GPIO.cleanup()