import time
import json
import paho.mqtt.client as mqtt
import numpy as np
import matplotlib.pyplot as plt
from math import atan,sin, cos, sqrt
from matplotlib.animation import FuncAnimation
from scipy.interpolate import splprep, splev
from copy import deepcopy

# --- CONFIGURATION ---
MQTT_BROKER = "10.60.247.146"  # CHANGE TO YOUR BROKER IP
MQTT_PORT = 1883
MQTT_TOPIC = "servos/sync_command"
noOfEsp=6  # Number of ESP devices to control

# How far in the future to schedule the FIRST move (seconds)
INITIAL_DELAY = 0.5 

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"✓ Connected successfully to {MQTT_BROKER}")
    else:
        print(f"✗ Connection failed with code: {reason_code}")

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print(f"Disconnected with reason code: {reason_code}")

# Use CallbackAPIVersion.VERSION2 to fix deprecation warning
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_disconnect = on_disconnect

# Try to connect with better error handling
print(f"Attempting to connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
except Exception as e:
    print(f"✗ Failed to connect: {e}")
    print("\nTroubleshooting steps:")
    print("1. Verify the MQTT broker is running")
    print("2. Check if 172.20.10.2 is the correct IP address")
    print("3. Ensure your firewall allows port 1883")
    print("4. Try pinging the broker: ping 172.20.10.2")
    exit(1)


def send_movement(esp1_angles, esp2_angles, esp3_angles,esp5_angles,esp6_angles,esp7_angles, delay_offset=0):
    """
    esp1_angles: [servo1, servo2]
    esp2_angles: [servo1, servo2]
    esp3_angles: [servo1, servo2] 
    delay_offset: seconds from NOW to execute
    """
    current_time = time.time()
    target_timestamp = int((current_time + INITIAL_DELAY + delay_offset) * 1000)

    payload = {
        "ts": target_timestamp,
        "data": {
            "ESP_01": esp1_angles,
            "ESP_02": esp2_angles,
            "ESP_03": esp3_angles,
          
            "ESP_05": esp5_angles,
            "ESP_06": esp6_angles,
            "ESP_07": esp7_angles
        }
    }
    
    result = client.publish(MQTT_TOPIC, json.dumps(payload), qos=0)
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"✓ Sent: {payload['data']} for Time: {target_timestamp}")
    else:
        print(f"✗ Failed to send message")

# NILESH CODE STARTS HERE
def spline_func(u):
    return splev(u, tck)  # Assuming you have tck from splprep

def euclidean_distance(p1, p2):
    return np.sqrt(np.sum((p1 - p2) ** 2))
# Initial point on the curve
x0, y0, z0 = 0, 0, 0  # You should choose an appropriate starting point


n=1
iterations =0
answers = []
error_margin=5
accuracylevel =100000
still_not_found =True
colors =['red','blue']
# User inputs for required number of segments, length, amplitudes, wavelength, and error margin
num_segments=noOfEsp+1#int(input("Enter the required number of segments: "))+1
req_length = 1.37#cad measured value #float(input("Enter the required length between two servo joints: "))
req_amplitude_z = 0.44#float(input("Enter the required amplitude in the z axis:"))
req_amplitude_y = 0#float(input("Enter the required amplitude in the y axis:"))
A1=0
num_path_points = 0
R=req_length/2#radius of the virtual rolling joint approximate sphere
approximation_circle_dist=0.37
# Initialize lists to store x and y coordinates, starts from origin
path_points_x = [0,3,4,20]
path_points_y = [0,3,4,20]
frequency = 4#ssssssssssssqfloat(input("Enter the frequency(number of sine waves ): ")) #I know that ive named it wavelength, but for some reason still sort of acting like frequency

# Take input for the coordinates
# for i in range(num_path_points):
#     x_coord = float(input(f"Enter x-coordinate of point {i+1}: "))
#     y_coord = float(input(f"Enter y-coordinate of point {i+1}: "))
#     path_points_x.append(x_coord)
#     path_points_y.append(y_coord)


# Convert lists to a numpy array
points = np.array([path_points_x, path_points_y])

# Create a parameterized spline
tck, u = splprep(points, s=0)

# Generate points along the spline
u_new = np.linspace(0, 1, accuracylevel)  # 10000 points along the spline, to increase accuracy(making it slower) just make that number larger(probably alsso change u from 0 to 1, to 2)
x_new, y_new = splev(u_new, tck)

# Calculate the derivatives (tangent vectors) along the spline
dx, dy = splev(u_new, tck, der=1)

# Normalize the tangent vectors
magnitude = np.sqrt(dx**2 + dy**2)
dx_normalized = -dy / magnitude
dy_normalized = dx / magnitude

# Set initial amplitude and frequency

# Create a 3D plot
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
plt.subplots_adjust(left=0.1, bottom=0.25)


# Set equal aspect ratio
ax.set_box_aspect([1, 1, 1])  # Aspect ratio is 1:1:1 in x:y:z

# Plot the original spline in 3D (XY plane)
ax.plot(x_new, y_new, np.zeros_like(x_new), label='Original Spline', color='red')


#plotting sine wave
# Initial sine wave plot in 3D
x_sine_wave =A1+ x_new + req_amplitude_y * np.sin(2 * np.pi *frequency * u_new) * dx_normalized
y_sine_wave = A1+y_new + req_amplitude_y * np.sin(2 * np.pi *frequency * u_new) * dy_normalized
z_wave = req_amplitude_z * np.abs(np.sin(2 * np.pi *frequency * u_new))

sine_wave_line, = ax.plot(x_sine_wave, y_sine_wave, z_wave, label='3D Spline with Sine Waves', color='green')
print(type(x_sine_wave),type(y_sine_wave))
print(x_sine_wave[1])


xyz = [[x_sine_wave[i], y_sine_wave[i], z_wave[i]] for i in range(len(x_sine_wave))]
xyz2=np.transpose(np.array([x_sine_wave,y_sine_wave,z_wave]))
print(xyz2[-1])


angles_ground_apparent =[]
angles_ground_real=[]
angles_relative=[]
angles_real =[]
answers_per_iteration =[]
angles_relative_per_iteration=[]
angles_real_per_iteration=[]

offset =0
answers_per_iteration.append([0,0,0])
while(offset<accuracylevel):
    # print("hi", end=':')
    for i in range(offset,len(x_sine_wave)):
        if(sqrt((x_sine_wave[i]-answers_per_iteration[-1][0])**2+(y_sine_wave[i]-answers_per_iteration[-1][1])**2+(z_wave[i]-answers_per_iteration[-1][2])**2)>req_length):
            answers_per_iteration.append([x_sine_wave[i],y_sine_wave[i],z_wave[i]])
        if(len(answers_per_iteration)==num_segments+1):
            # Calculate angles relative to the ground and relative to previous segment
            # answers_per_iteration=np.array(answers_per_iteration)
            for j in range(0,len(answers_per_iteration)-1):
                angles_ground_apparent.append([atan((answers_per_iteration[j+1][1]-answers_per_iteration[j][1])/(answers_per_iteration[j+1][0]-answers_per_iteration[j][0]))*180/np.pi,atan((answers_per_iteration[j+1][2]-answers_per_iteration[j][2])/(answers_per_iteration[j+1][0]-answers_per_iteration[j][0]))*180/np.pi])
                #still needs to be verified if this is correct way of finding the real angles
                angles_ground_real.append([atan((answers_per_iteration[j+1][1]-answers_per_iteration[j][1])/sqrt((answers_per_iteration[j+1][0]-answers_per_iteration[j][0])**2+(answers_per_iteration[j+1][2]-answers_per_iteration[j][2])**2))*180/np.pi,atan((answers_per_iteration[j+1][2]-answers_per_iteration[j][2])/sqrt((answers_per_iteration[j+1][0]-answers_per_iteration[j][0])**2+(answers_per_iteration[j+1][1]-answers_per_iteration[j][1])**2))*180/np.pi])
                if j:
                    angles_relative_per_iteration.append(tuple([round(180+angles_ground_apparent[j][0]-angles_ground_apparent[j-1][0],3),round(180+angles_ground_apparent[j][1]-angles_ground_apparent[j-1][1],3)]))
                    angles_real_per_iteration.append(tuple([round(180+angles_ground_real[j][0]-angles_ground_real[j-1][0],3),round(180+angles_ground_real[j][1]-angles_ground_real[j-1][1],3)]))
            break
    # print("This: ", angles_real_per_iteration)
    # print(angles_real_per_iteration)
    # sleep(0.065)
    if(len(answers_per_iteration)<num_segments+1):
        break
    # print("Then This appends...")
    answers.append(deepcopy(answers_per_iteration))#normal copy was giving some issues


    angles_real.append(deepcopy(angles_real_per_iteration))
    # print(angles_real)
    angles_relative.append(deepcopy(angles_relative_per_iteration))
    answers_per_iteration.clear()
    angles_real_per_iteration.clear()
    angles_ground_apparent.clear()
    angles_ground_real.clear()


    angles_relative_per_iteration.clear()
    offset+=int(accuracylevel/150)
    answers_per_iteration.append([x_sine_wave[offset],y_sine_wave[offset],z_wave[offset]])


for item in angles_real:
    print(item)#(horizontal,vertial)


# print(len(angles_real))



# answers=np.array(answers)
# # print(answers)
# ans_x=answers[:,0]
# ans_y=answers[:,1]
# ans_z=answers[:,2]
# # print(ans_x)
# ax.plot(ans_x,ans_y,ans_z,'bo-',label=f'Segments along path')
max_dist =max(max(path_points_x),max(path_points_y))
ax.set_xlim(0,max_dist)
ax.set_ylim(0,max_dist)
ax.set_zlim(0,max_dist)


# plotting animation wali cheez

line, = ax.plot([], [], [], 'o-', lw=2)
def update(frame):
    """Update function for animation"""
    data = np.array(answers[frame])  # Get points for the current frame
    x, y, z = data[:, 0], data[:, 1], data[:, 2]
    # Update line data
    line.set_data(x, y)
    line.set_3d_properties(z)
    return line,

ani = FuncAnimation(fig, update, frames=len(answers), interval=50, blit=False)

plt.legend()
plt.grid(True)
plt.show()



tempcount = 1
wantToSend=True
i=1

while(wantToSend):
    for angles_set in angles_real:
        print(f"Sending sequence: {tempcount}")
        
        # 1. Create a list to store the data for all 3 ESPs
        # It will look like: [ [95,60], [90,89], [89,120] ]
        row_data = [] 
        
        for angle_pair in angles_set:
            # --- Your existing Math ---
            angle_1 = atan(R*sin((180-angle_pair[0])*np.pi/180)/(R*cos((180-angle_pair[0])*np.pi/180)-approximation_circle_dist))*180/np.pi
            angle_2 = atan(R*sin((180-angle_pair[1])*np.pi/180)/(R*cos((180-angle_pair[1])*np.pi/180)-approximation_circle_dist))*180/np.pi
            
            # --- Calculate the final integer values ---
            val1 = int(min(120, max(90 - int(angle_1), 60)))
            val2 = int(min(120, max(90 - int(angle_2), 60)))

            # 2. Append as a pair of numbers [x, y] to our list
            row_data.append([val1, val2])

        # 3. Send the movement if we have data for all 3 ESPs
        if len(row_data) >= 3:
            # Note: We use square brackets [] for lists in Python, not ()
            send_movement(
                row_data[0], 
                row_data[1], 
                row_data[2], 
                row_data[3],
                row_data[4],
                row_data[5],
                delay_offset=(tempcount * 0.3)
            )
        
        # Optional: Print what we just sent for debugging
        print(row_data)

        # 4. Increment counter
        tempcount += 1
        
        # Note: If you want to schedule them all instantly, remove this sleep.
        # If you want to pace the loop execution, keep it.
        # if(keyboard.is_pressed('p')):
        #     print("paused")
        #     time.sleep(2)

        #     while(True):
        #         if(keyboard.is_pressed('p')):
        #             # print("continuing")
        #             time.sleep(2)
        #             break
        #         if(keyboard.is_pressed('q')):
        #             print("quitting")
        #             wantToSend=False
        #             break
        # if(not wantToSend):
        #     print("hi")
        #     break
        # response = ser.readline().decode().strip()  # Read   serial buffer5
        # time.sleep(10)
        # if response:    
        #     print(f"Received: {response}")  # Print received data
    # print("Serial communication finished.")
    # if(input("Press R to restart sending angle commands: ").upper()!='R'):
    #     print("Ending Execution")
    #     ser.close()  # Close serial connection
    #     break
    # else :
    #     print("Restarting angle commands")

time.sleep(1)

try:
    while True:
        print("\n" + "="*50)
        print("1. Send Immediate Move")
        print("2. Send Sequence (3 moves)")
        print("3. Exit")
        print("="*50)
        choice = input("Select: ")

        if choice == '1':
            try:
                e1s1 = int(input("ESP1 S1 (0-180): "))
                e1s2 = int(input("ESP1 S2 (0-180): "))
                e2s1 = int(input("ESP2 S1 (0-180): "))
                e2s2 = int(input("ESP2 S2 (0-180): "))
                send_movement([e1s1, e1s2], [e2s1, e2s2])
            except ValueError:
                print("✗ Please enter valid numbers")
            
        elif choice == '2':
            c = 0
            v = 0
            b = 0
            for i in range(20):
                print("\nSending 20 moves spaced 1 second apart...")
                c+=9
                v+=10
                b+=11
                clean_c = 180 - abs(c % 360 - 180)
                clean_v = 180 - abs(v % 360 - 180)
                clean_b = 180 - abs(b % 360 - 180)
                # Move 1: t + 0.5s
                send_movement([clean_c, clean_c], [clean_v,clean_v],[clean_b,clean_b], delay_offset= (i*0.02))
                time.sleep(0.01)  # Small delay between publishes
            
            print("✓ All moves queued")
            
        elif choice == '3':
            break
        else:
            print("✗ Invalid choice")

except KeyboardInterrupt:
    print("\n\nShutting down...")
finally:
    client.loop_stop()
    client.disconnect()
    print("✓ Disconnected")