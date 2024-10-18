import subprocess

def start_pigpiod():
    try:
        subprocess.run(['sudo','killall', 'pigpiod'], check=True)
    except:
        pass
    try:
        subprocess.run(['sudo', 'pigpiod'], check=True)
    except subprocess.CalledProcessError as e:
        #print(f"Failed to start pigpiod: {e}")
        pass