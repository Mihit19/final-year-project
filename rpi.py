import paho.mqtt.client as mqtt
import time
import pyrebase

# Firebase configuration (same as before)
config = {
    "apiKey": "AIzaSyDt27zrAPbFweDWMUKTsfkT1j_oyxwCFPo",
    "authDomain": "smart-dustbin-539ee",
    "databaseURL": "https://smart-dustbin-539ee-default-rtdb.firebaseio.com",
    "storageBucket": "smart-dustbin-539ee.appspot.com"
}

dustbin_original_level = 100
firebase = pyrebase.initialize_app(config)
database = firebase.database()

# MQTT Settings
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_COMMANDS = "smartdustbin/commands"
TOPIC_RESPONSES = "smartdustbin/responses"

# Global variables for MQTT
response_received = None
client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code "+str(rc))
    client.subscribe(TOPIC_RESPONSES)

def on_message(client, userdata, msg):
    global response_received
    response_received = msg.payload.decode()
    print(f"Received: {response_received}")

def send_command(command, timeout=2):
    global response_received
    response_received = None
    client.publish(TOPIC_COMMANDS, command)
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if response_received is not None:
            return response_received
        time.sleep(0.1)
    return None

def get_ultra_data():
    response = send_command("get_ultra")
    if response:
        database.child("WasteLevel").set(response)
        return int(response)
    return None

def get_gas_data():
    response = send_command("get_gas")
    if response:
        database.child("GasLevel").set(response)
        return int(response)
    return None

def get_ir_status():
    response = send_command("get_ir", timeout=1.5)
    if response in ["Detected", "Not Detected"]:
        return response
    return "Not Detected"

def lid_control():
    ir_status = get_ir_status()
    print(ir_status)
    if ir_status == "Detected":
        send_command("open_lid")
        print("Lid Opened")
    else:
        send_command("close_lid")
        print("Lid Closed")

def register_user_to_firebase(user_id, name):
    user_data = {
        "name": name,
        "voted": False
    }
    database.child("users").child(user_id).set(user_data)
    print(f"User {user_id} registered in Firebase with name: {name}")

def arduino_register_command(user_id):
    while True:
        print("register: ", user_id)
        response = send_command(f"register{user_id}", timeout=3)
        print("response inside while loop : ", response)
        if response == "registration_success":
            print(f"Fingerprint for User ID: {user_id} successfully registered.")
            return True
        elif response == "registration_failed":
            print("Fingerprint registration failed. Retrying...")
            continue
    return False

def clear_users():
    response = send_command("clear_all_users")
    print(response)

def verify_fingerprint():
    while True:
        response = send_command("verify", timeout=3)
        print(response)
        if response and response.isnumeric():
            print(f"Fingerprint matched for User ID: {response}")
            user_data = database.child("users").child(response).get().val()
            if user_data:
                send_command("open_lid")
                print("User verified")
                database.child("Dustbin/verify").set("False")
                return True
            else:
                print("User ID not found in Firebase.")
                return False

def UV_LED():
    response = send_command("uv_led", timeout=10)
    if response == "sterilised":
        return True
    return False

def bin_status_update(status):
    while True:
        if status == "normal":
            database.child("Dustbin/Status").set("Dustbin Full. Please Collect!")
        elif status == "biohazard":
            database.child("Dustbin/Status").set("Dustbin is biohazardous. Please Collect!")
            verify = database.child("Dustbin/verify").get().val()
            if verify:
                print("Verifying fingerprint...")
                verify_fingerprint()
        
        x = database.child("DustbinStatus").get().val()
        if x != "Waste Collected":
            print("Please collect waste!!")
        else:
            x = UV_LED()
            return x

def compaction():
    response = send_command("compaction", timeout=20)
    if response == "Compaction done":
        return True
    return False

# Initialize MQTT client
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

try:
    send_command("close_lid")
    print("Start. (CTRL + C to Exit.)")
    
    while True:
        register_request = database.child("users/register").get().val()
        if register_request == "true":
            user_id = database.child("users/next_user_id").get().val()
            user_name = database.child("users/next_user_name").get().val()

            if user_id and user_name:
                if arduino_register_command(user_id):
                    register_user_to_firebase(user_id, user_name)
                    database.child("users/register").set("false")
                    print("Registration complete.")
                else:
                    print("Fingerprint registration unsuccessful. Aborting...")
            else:
                print("User ID or Name missing in Firebase.")
        
        flag2 = bin_status_update(status)
        compactionflag = True
        while flag2:
            lid_control()
            dist = get_ultra_data()
            gaslevel = get_gas_data()
            print(gaslevel)
            print(dist)
            
            if gaslevel and gaslevel >= 400:
                send_command("close_lid")
                flag2 = False
                status = "biohazard"
            else:
                if dist and dist < 10:
                    send_command("close_lid")
                    time.sleep(2)
                    if compactionflag:
                        status = compaction()
                    else:
                        status = "normal"
                        flag2 = False
                    
                    x = dustbin_original_level - dist
                    if status:
                        dist = get_ultra_data()
                        print(dist)
                        if dist:
                            y = dustbin_original_level - dist
                            efficiency = (x/y)*100 if y != 0 else 0
                            if efficiency < 8:
                                compactionflag = False
                            else:
                                compactionflag = True
                            if dist < 10:
                                status = "normal"
                                flag2 = False
                            else:
                                database.child("DustbinStatus").set("Dustbin Not Full")
            
            mancom = database.child("ManualControl").get().val()
            if mancom == "Compaction":
                status = compaction()
                database.child("ManualControl").remove()
            elif mancom == "OpenLid":
                send_command("open_lid")
                database.child("ManualControl").remove()
            elif mancom == "CloseLid":
                send_command("close_lid")
                database.child("ManualControl").remove()
        
        time.sleep(1.5)

except KeyboardInterrupt:
    print("Exit.")
    client.loop_stop()
    client.disconnect()
