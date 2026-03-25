import time
import os
import logging
from datetime import datetime

import board
import requests
import adafruit_bme280.advanced as adafruit_bme280
import adafruit_bh1750
from dotenv import load_dotenv

# --- Konfiguracja ---
load_dotenv()
THINGSPEAK_API_KEY = os.getenv("THINGSPEAK_API_KEY")
THINGSPEAK_URL = "https://api.thingspeak.com/update"
INTERVAL_S = 60

# --- Logowanie ---
logging.basicConfig(
    filename=os.path.expanduser("~/weather-station/logs/weather.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# --- Inicjalizacja czujników ---
i2c = board.I2C()
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
bh1750 = adafruit_bh1750.BH1750(i2c, address=0x23)


def read_sensors():
    """Odczytuje dane ze wszystkich czujników."""
    return {
        "temperature": round(bme280.temperature, 2),
        "humidity": round(bme280.relative_humidity, 2),
        "pressure": round(bme280.pressure, 2),
        "light": round(bh1750.lux, 2),
    }


def send_to_thingspeak(data):
    """Wysyła dane do chmury ThingSpeak."""
    payload = {
        "api_key": THINGSPEAK_API_KEY,
        "field1": data["temperature"],
        "field2": data["humidity"],
        "field3": data["pressure"],
        "field4": data["light"],
    }
    try:
        response = requests.post(THINGSPEAK_URL, data=payload, timeout=10)
        if response.status_code == 200 and int(response.text) > 0:
            logging.info(f"OK — wysłano: {data}")
            print(f"[{datetime.now():%H:%M:%S}] OK — {data}")
        else:
            logging.warning(f"Błąd HTTP {response.status_code}: {response.text}")
    except Exception as e:
        logging.error(f"Błąd połączenia: {e}")


# --- Pętla główna ---
if __name__ == "__main__":
    print("Stacja pogodowa uruchomiona!")
    logging.info("Start stacji pogodowej")
    while True:
        data = read_sensors()
        send_to_thingspeak(data)
        time.sleep(INTERVAL_S)
