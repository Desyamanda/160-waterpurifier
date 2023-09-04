import telepot
import time
import RPi.GPIO as GPIO
from w1thermsensor import W1ThermSensor
import Adafruit_ADS1x15
import requests
from ubidots import ApiClient


# Konfigurasi GPIO
GPIO.setmode(GPIO.BCM)

# Konfigurasi pin GPIO untuk ultrasonik
GPIO_TRIGGER = 12
GPIO_ECHO = 6
GPIO.setup(GPIO_TRIGGER, GPIO.OUT)
GPIO.setup(GPIO_ECHO, GPIO.IN)

# Konfigurasi pin GPIO untuk sensor suhu
GPIO_TEMP = 4  

# Konfigurasi pin GPIO untuk relay
relay1_pin = 23
relay2_pin = 24
GPIO.setup(relay1_pin, GPIO.OUT)
GPIO.setup(relay2_pin, GPIO.OUT)

# Konfigurasi ADC
adc = Adafruit_ADS1x15.ADS1115()


#Data Digital
Filter = 0

# Konfigurasi pH kalibrasi
KALIBRASI_PH = False  
NILAI_PH_KALIBRASI = 9.18  
SAMPLING_KALIBRASI = 200  

# Konstanta untuk perhitungan pH
Offset = NILAI_PH_KALIBRASI
k = 2.31838565

# Konfigurasi pengambilan data pH
sampling_interval = 2000  
array_length = 40
pH_array = [0] * array_length
pH_array_index = 0

# Konfigurasi sensor suhu
sensor = W1ThermSensor()

# Inisialisasi koneksi ke Ubidots
TOKEN = "BBFF-xOmQsyl2NLW3gvXYx3DbT9rk4hwqWJ"
DEVICE_LABEL = "water-purifier"
VARIABLE_LABEL_1 = "temperature-sensor"
VARIABLE_LABEL_2 = "ph-sensor"
VARIABLE_LABEL_3 = "ultrasonic-sensor"
VARIABLE_LABEL_4 = "filter"

# Inisialisasi koneksi ke Telegram
TELEGRAM_BOT_TOKEN = "6529561850:AAEj8nCwAtkcS7M_Qc1BQrnuSJ7NM1AIeAk"
TELEGRAM_CHAT_ID = "1085802754"
TELEGRAM_BOT_USERNAME = "@water_purifier_bot" 
bot = telepot.Bot(TELEGRAM_BOT_TOKEN)



def distance():
    GPIO.output(GPIO_TRIGGER, True)
    time.sleep(0.00001)
    GPIO.output(GPIO_TRIGGER, False)
    StartTime = time.time()
    StopTime = time.time()
    while GPIO.input(GPIO_ECHO) == 0:
        StartTime = time.time()
    while GPIO.input(GPIO_ECHO) == 1:
        StopTime = time.time()
    TimeElapsed = StopTime - StartTime
    distance = (TimeElapsed * 34300) / 2
    return distance

def average_array(arr):
    return sum(arr) / len(arr)

def read_ph_value(voltage):
    return k * voltage

try:
    while True:
        # Mengambil data jarak
        jarak = distance()
        print("Jarak air saat ini = %.1f cm" % jarak)
        
        # Mengambil data suhu
        temperature = sensor.get_temperature()
        print("Suhu air saat ini = %.2f Celsius" % temperature)
        
        # Mengambil data pH
        voltage = adc.read_adc(0, gain=1) * (5.0 / 32767)
        pH_value = read_ph_value(voltage)
        pH_array[pH_array_index] = voltage
        pH_array_index = (pH_array_index + 1) % array_length
        avg_voltage = average_array(pH_array)
        pH_value = read_ph_value(avg_voltage)
        print("Tegangan = {:.4f}    Nilai pH = {:.2f}".format(avg_voltage, pH_value))

   ##New Program##
        ##Relay 1 = Normally Close##
        ##Relay 2 = Normally Open##
        if jarak>50:
            if pH_value <7:
                GPIO.output(relay1_pin, GPIO.HIGH)
                GPIO.output(relay2_pin, GPIO.HIGH)
                Filter = 1
                print("Relay 1: Aktif (Mengalirkan Air)   Relay 2: Aktif (Stop Air)")
            elif pH_value >9:
                GPIO.output(relay1_pin, GPIO.HIGH)
                GPIO.output(relay2_pin, GPIO.HIGH)
                Filter = 1
                print("Relay 1: Aktif (Mengalirkan Air)   Relay 2: Aktif (Stop Air)")
            elif pH_value >=7:
                GPIO.output(relay1_pin, GPIO.LOW)
                GPIO.output(relay2_pin, GPIO.LOW)
                Filter = 0
                print("Relay 1: Non Aktif (Stop Air)   Relay 2: Non Aktif (Mengalirkan Air)")
            elif pH_value <=9:
                GPIO.output(relay1_pin, GPIO.LOW)
                GPIO.output(relay2_pin, GPIO.LOW)
                Filter = 0
                print("Relay 1: Non Aktif (Stop Air)   Relay 2: Non Aktif (Mengalirkan Air)")
        elif jarak<25:
            GPIO.output(relay1_pin, GPIO.LOW)
            GPIO.output(relay2_pin, GPIO.HIGH)
            Filter = 0
            print("Relay 1: Non Aktif (Stop Air)   Relay 2: Aktif (Stop Air)")
            
            # Mengirim data ke Ubidots
        payload = {
            "temperature-sensor": temperature,
            "ph-Sensor": pH_value,
            "ultrasonic-sensor": jarak,
            "filter": Filter
        }
    
        headers = {"X-Auth-Token": TOKEN, "Content-Type": "application/json"}
        url = "http://industrial.api.ubidots.com"
        url = "{}/api/v1.6/devices/{}".format(url, DEVICE_LABEL)
        req = requests.post(url=url, headers=headers, json=payload)
    
        print(req.status_code, req.json())
        if req.status_code >= 400:
            print("[ERROR] Could not send data to Ubidots")
        else:
            print("[INFO] Data sent to Ubidots successfully")

        time.sleep(1)
        
        if  pH_value<7 or pH_value>9 or jarak > 50:
            filter_status ="Filter sedang aktif"  # Filter aktif jika pH di luar batas normal
        else:
            filter_status ="Filter sedang non aktif"  # Filter non aktif jika pH dalam batas normal
        if jarak < 25:
            filter_status ="Filter sedang non aktif"  # Filter non aktif jika jarak di bawah 25
        
        #NEW PROGRAM#
        telegram_status = "SAAT INI AIR SEDANG MENGALIR" if jarak >50 else "Penampungan air terisi"
        
        if jarak > 50 :
            telegram_message = (
                f" {telegram_status}\n"
                f" {filter_status}\n"
                f" Suhu air     : {temperature:.2f} Celsius\n"
                f" Nilai pH air : {pH_value:.2f}"
                
            )

            bot.sendMessage(TELEGRAM_CHAT_ID, telegram_message)
    
except KeyboardInterrupt:
    print("Measurement stopped by User")
    GPIO.cleanup()

