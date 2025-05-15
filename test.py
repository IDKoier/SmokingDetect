import uuid

def get_mac_address():
    mac = ':'.join(['{:02x}'.format((uuid.getnode()   >> 8*i) & 0xff) for i in range(5, -1, -1)])
    return mac
    
print(get_mac_address())