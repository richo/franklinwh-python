#!/usr/bin/env python
import sys
import requests
import hashlib
import binascii


LOGIN_URL = "https://energy.franklinwh.com/hes-gateway/terminal/initialize/appUserOrInstallerLogin"

def _login(email, password):
    digest = hashlib.md5(password.encode()).hexdigest()
    params = {
            "account": email,
            "lang": "EN_US",
            "password": digest,
            "type": "1",
            }

    req = requests.post(LOGIN_URL, data=params)
    try:
        j = req.json()
        return j["result"]["token"]
    except:
        import pdb
        pdb.set_trace()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: {} email password".format(sys.argv[0]))
        sys.exit(1)
    token = _login(sys.argv[1], sys.argv[2])
    print("Your token is")
    print("  {}".format(token.replace("APP_ACCOUNT:", "")))
    print("Use this in your hass config")



