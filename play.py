#!/usr/bin/env python3

import os
import sys
import subprocess
import threading
import time
import re
import requests
from threading import Semaphore

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
BOLD = "\033[1m"

total_levels = 10
user_file_path = os.path.expanduser("~/.wlug_user")
sem = Semaphore(2)
levels_pulled = 0
loading_done = False

# BACKEND_URL = "http://localhost:3000"
BACKEND_URL = "https://ctf-backend-5yhk.onrender.com"

def get_username():
    """Get or prompt for username, save in ~/.ctf_user"""
    if os.path.isfile(user_file_path):
        with open(user_file_path, "r") as f:
            username = f.read().strip()
            if username:
                print(f"{BOLD}{YELLOW}Welcome back, {username}!{RESET}")
                return username
    username = ""
    while not username:
        username = input(f"{BOLD}{MAGENTA}Enter your CTF username: {RESET}").strip()
    with open(user_file_path, "w") as f:
        if not re.match(r"^LD\d+$", username):
            print(f"{BOLD}{RED}Invalid username!{RESET}")
            return get_username()
        f.write(username)

    print(f"{BOLD}{YELLOW}Your username is set to {username}.{RESET}")
    return username

def check_internet():
    try:
        subprocess.check_call(["ping", "-c", "2", "google.com"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{BOLD}{GREEN}Internet is working! Great.{RESET}")
        return True
    except subprocess.CalledProcessError:
        return False

def are_you_sudo():
    return os.geteuid() == 0

def get_os():
    if sys.platform.startswith("linux"):
        try:
            with open("/etc/os-release") as f:
                lines = f.read().lower()
                if "ubuntu" in lines: return "Ubuntu"
                if "debian" in lines: return "Debian"
                if "centos" in lines: return "CentOS"
                if "red hat" in lines: return "RHEL"
                if "fedora" in lines: return "Fedora"
                if "arch" in lines: return "Arch"
        except Exception: pass
    elif sys.platform == "darwin":
        return "MacOS"
    return "Unknown"

def restart_docker():
    os_type = get_os()
    if os_type == "MacOS":
        result = subprocess.call("brew services restart docker > /dev/null 2>&1", shell=True)
        if result == 0:
            print(f"{BOLD}{GREEN}Docker was successfully restarted using brew!{RESET}")
            return True
    elif os_type in ["Ubuntu", "Debian", "CentOS", "Fedora", "RHEL", "Arch"]:
        result = subprocess.call("systemctl restart docker > /dev/null 2>&1", shell=True)
        if result == 0:
            print(f"{BOLD}{GREEN}Docker was successfully restarted{RESET}")
            return True
    else:
        print(f"{BOLD}{RED}Unsupported OS. Cannot restart Docker automatically.{RESET}")
        return False
    return False

def check_and_get_docker():
    is_docker_ok = subprocess.call("docker images > /dev/null 2>&1", shell=True)
    if is_docker_ok == 0:
        print(f"{BOLD}{BLUE}Docker already exists!{RESET}")
        return True
    if restart_docker():
        return True
    print(f"{BOLD}{YELLOW}Docker is not installed. Attempting installation...{RESET}")
    os_type = get_os()
    install_status = -1
    if os_type in ["Ubuntu", "Debian"]:
        install_status = subprocess.call("sudo apt update && sudo apt install -y docker.io curl", shell=True)
    elif os_type in ["CentOS", "RHEL"]:
        install_status = subprocess.call("sudo yum install -y docker curl", shell=True)
    elif os_type == "Fedora":
        install_status = subprocess.call("sudo dnf install -y docker curl", shell=True)
    else:
        print("Unsupported OS. Please install Docker manually.")
        return False
    if install_status == 0:
        print(f"{BOLD}{GREEN}Docker installation successful!{RESET}")
        return restart_docker()
    print("Docker installation failed. Please install manually or rerun the script.")
    return False

def loader_animation():
    global loading_done, levels_pulled
    spinner = ['|', '/', '-', '\\']
    i = 0
    while not loading_done:
        progress = (levels_pulled / 2) * 100  
        bar_width = 30
        pos = int(levels_pulled * bar_width / 2)
        bar = "#" * pos + "-" * (bar_width - pos)
        print(f"\r[{bar}] {progress:.1f}% {spinner[i%4]} ({levels_pulled}/2) ", end="", flush=True)
        i += 1
        time.sleep(0.2)
    print("\rLevels pulled successfully!")

def pull_level(level, silent=False):
    global levels_pulled
    tag = f"war{level}"
    docker_image = f"ghcr.io/avadhutmali/linuxdiary6.0-wargames-level:{tag}"
    
    # Check if level is already pulled
    check_image = f"docker images -q {docker_image} 2>/dev/null"
    result = subprocess.run(check_image, shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        if not silent:
            print(f"{GREEN}Level {level} already available!{RESET}")
        levels_pulled += 1  # Increment even if already exists during initial setup
        return True
    
    if not silent:
        print(f"{YELLOW}Pulling level {level}...{RESET}")
    
    for attempts in range(3):
        get_level = f"docker pull {docker_image} > /dev/null 2>&1"
        exit_status = subprocess.call(get_level, shell=True)
        if exit_status == 0:
            if not silent:
                print(f"{GREEN}Level {level} pulled successfully!{RESET}")
            levels_pulled += 1
            return True
        time.sleep(3)
    
    if not silent:
        print(f"{RED}Failed to pull level {level} after 3 attempts{RESET}")
    return False

def pull_next_level_async(level):
    """Pull the next level in background without blocking the main thread"""
    def pull_in_background():
        if level <= total_levels:
            tag = f"war{level}"
            docker_image = f"ghcr.io/avadhutmali/linuxdiary6.0-wargames-level:{tag}"
            
            # Check if level is already pulled
            check_image = f"docker images -q {docker_image} 2>/dev/null"
            result = subprocess.run(check_image, shell=True, capture_output=True, text=True)
            if result.stdout.strip():
                return True  # Already available
            
            # Pull the level (don't increment levels_pulled counter for background pulls)
            for attempts in range(3):
                get_level = f"docker pull {docker_image} > /dev/null 2>&1"
                exit_status = subprocess.call(get_level, shell=True)
                if exit_status == 0:
                    return True
                time.sleep(3)
            return False
    
    thread = threading.Thread(target=pull_in_background)
    thread.daemon = True  # Dies when main program exits
    thread.start()

def pull_initial_levels(current_level):
    """Pull current level and next level only with loader animation"""
    global loading_done, levels_pulled
    print("Getting levels...! Patience is the key.")
    loading_done = False
    levels_pulled = 0
    
    # Start loader animation in background
    loader_thread = threading.Thread(target=loader_animation)
    loader_thread.start()
    
    # Pull current level
    if not pull_level(current_level, silent=True):
        loading_done = True
        loader_thread.join()
        print(f"{RED}Failed to pull current level {current_level}!{RESET}")
        return False
    
    # Pull next level if it exists
    if current_level + 1 <= total_levels:
        if not pull_level(current_level + 1, silent=True):
            loading_done = True
            loader_thread.join()
            print(f"{RED}Failed to pull next level {current_level + 1}!{RESET}")
            return False
    
    loading_done = True
    loader_thread.join()
    return True

def setup(current_level=0):
    if not are_you_sudo():
        print(f"{BOLD}{RED}Run the script with sudo!{RESET}")
        return 1
    os.system("clear")
    if not check_internet():
        print(f"{BOLD}{RED}Please check your internet connection.{RESET}")
        return 1
    if not check_and_get_docker():
        print(f"{BOLD}Error getting docker!{RESET}")
        return 1
    if not pull_initial_levels(current_level):
        print(f"{BOLD}Error pulling levels!{RESET}")
        return 1
    os.system("clear")
    return 0

def check_file():
    if os.path.isfile(user_file_path):
        with open(user_file_path, "r") as f:
            if f.read().strip():
                print("Setup already performed!")
                return True
        return False
    return False

def get_current_level(user_id):
    """Fetch the current level from backend for the specific user."""
    try:
        resp = requests.get(f"{BACKEND_URL}/getLevel", params={"userId": user_id})
        if resp.status_code == 200:
            return resp.json().get("level", 0)
    except Exception as e:
        print(f"Could not connect to backend: {e}")
    return -1

def print_section_header(title):
    print(f"{BOLD}{MAGENTA}┌──────────────────────────────────────┐{RESET}")
    print(f"{BOLD}{MAGENTA}│ {title}{RESET}{BOLD}{MAGENTA}{' ' * (38 - len(title) - 1)}│{RESET}")
    print(f"{BOLD}{MAGENTA}└──────────────────────────────────────┘{RESET}")

def submit_flag(flag, user_id):
    """Submit flag to backend for the specific user."""
    try:
        resp = requests.post(f"{BACKEND_URL}/checkFlag", json={"flag": flag, "userId": user_id})
        if resp.status_code == 200:
            result = resp.json()
            return result['correct'], result['newLevel']
        else:
            print("Error submitting flag. Backend error.")
            return False, None
    except Exception as e:
        print(f"Could not connect to backend: {e}")
        return False, None


def interactive_level_shell(level_name, level_num, user_id):
    # Start docker container if not already running
    check_container = f"docker ps -a --format '{{{{.Names}}}}' | grep -w {level_name} > /dev/null 2>&1"
    container_exists = subprocess.call(check_container, shell=True)
    tag = f"war{level_num}"
    docker_image = f"ghcr.io/avadhutmali/linuxdiary6.0-wargames-level:{tag}"
    if container_exists != 0:
        if level_num == 10:
            # Custom run command for level 10
            level_string = (
                f"docker run -dit --privileged --name {level_name} "
                f"{docker_image} /bin/sh > /dev/null 2>&1" # Maybe bash instead of sh
            )
        elif level_num == 6:
            level_string = (
                f"docker run -dit --hostname {user_id} --name {level_name} "
                f"{docker_image} > /dev/null 2>&1"
            )
        else:
            # Default run command
            level_string = (
                f"docker run -dit --hostname {user_id} --name {level_name} "
                f"{docker_image} /bin/sh > /dev/null 2>&1"
            )

        exit_code = subprocess.call(level_string, shell=True)
        if exit_code != 0:
            print("Failed to start container. Exiting...")
            return False

    print_section_header(f"Welcome {user_id}, to Wargames Level {level_num}")
    print(f"{GREEN}{BOLD}Submit the flag using 'submit FLAG{{...}}' below.{RESET}")
    print(f"{GREEN}{BOLD}Type 'play' to open your Docker shell. Type 'exit' to quit this level session.{RESET}")

    while True:
        try:
            user_input = input(f"{BOLD}{MAGENTA}level-{level_num}>{RESET} ").strip()
        except EOFError:
            break
        if user_input.lower().startswith("submit "):
            flag = user_input[7:].strip()
            correct, new_level = submit_flag(flag, user_id)
            if correct:
                print(f"{GREEN}{BOLD}Correct flag! Level up!{RESET}")
                # Pull next level in background before removing current container
                if new_level and new_level + 1 <= total_levels:
                    pull_next_level_async(new_level + 1)
                # Remove container
                remove_container = f"docker rm -f {level_name} > /dev/null 2>&1"
                subprocess.call(remove_container, shell=True)
                return new_level
            else:
                print(f"{RED}{BOLD}Incorrect flag. Try again.{RESET}")
        elif user_input.lower() == "play":
            attach_command = f"docker start {level_name} > /dev/null 2>&1 && docker exec -it {level_name} sh"
            os.system(attach_command)
        elif user_input.lower() == "exit":
            print("Exiting current level session.")
            return level_num
        else:
            print("Unknown command. Use 'submit FLAG{...}', 'play', or 'exit'.")

def main():
    global total_levels
    if len(sys.argv) > 1 and sys.argv[1] == "-r":
        print_section_header("Resetting User....")
        print("User reset is disabled in this version.")
        return
    
    user_id = get_username()
    print(f"{GREEN}{BOLD}Welcome, {user_id}! Preparing your game session...{RESET}")
    current_level = get_current_level(user_id)
    if current_level == -1:
        print(f"{BOLD}Either the backend is down or there is issue in the database{RESET}")
        return
    
    if not check_file():
        if setup(current_level) == 1:
            return
    else:
        if setup(current_level) == 1:
            return
        # Even if setup was done before, ensure current and next level are available
        print("Checking level availability...")
        # Check current level without affecting levels_pulled counter
        tag = f"war{current_level}"
        docker_image = f"ghcr.io/avadhutmali/linuxdiary6.0-wargames-level:{tag}"
        check_image = f"docker images -q {docker_image} 2>/dev/null"
        result = subprocess.run(check_image, shell=True, capture_output=True, text=True)
        if not result.stdout.strip():
            # Need to pull current level
            if not pull_level(current_level, silent=True):
                print(f"{RED}Failed to ensure current level {current_level} is available{RESET}")
                return
        
        if current_level + 1 <= total_levels:
            pull_next_level_async(current_level + 1)
    
    while current_level <= total_levels:
        os.system("clear")
        level_name = f"ctf{current_level}"
        new_level = interactive_level_shell(level_name, current_level, user_id)
        if new_level is None:
            break
        if new_level > current_level:
            current_level = new_level
        else:
            break
    # Only print congratulations if actually completed all levels
    if current_level > total_levels:
        print(f"{BOLD}{GREEN}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}{GREEN}  🎉 Congratulations! You completed the WARGAMES! 🎉{RESET}")
        print(f"{BOLD}{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    else:
        print(f"{BOLD}{GREEN}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
        print(f"{BOLD}{GREEN}                    Try Again                    {RESET}")
        print(f"{BOLD}{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    # print(f"File path: {user_file_path}")

if __name__ == "__main__":
    main()
