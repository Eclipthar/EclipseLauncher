import requests

def get_uuid(username):
    r = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{username}")
    if r.status_code == 200:
        return r.json()["id"]
    else:
        print("Invalid username!")
        return None

uuid = get_uuid("Notch")
if uuid:
    print(f"UUID for Notch: {uuid}")
