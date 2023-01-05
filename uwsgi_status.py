#!/usr/bin/env python3

import socket, io, json, datetime

socket_fn = "/tmp/uwsg_govtrack_www_stats.sock"

# Read the stats server raw output.
buffer = io.BytesIO()
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.connect(socket_fn)
    while True:
        data = client.recv(4096)
        if len(data) == 0: break
        buffer.write(data)
    client.close()
buffer.seek(0)

# Parse the stats server output as JSON.
stats = json.load(buffer)

# Flatten the list of cores across the workers.
def clone_dict_without_key(d, *kk):
    d = dict(d) # clone
    for k in kk:
        del d[k] # remove keys
    return d
cores = []
for worker in stats['workers']:
    for core in worker['cores']:
        # Parse the request start times from UNIX time to datetime instances.
        if 'request_start' in core['req_info']:
            core['req_info']['request_start'] = request_start = datetime.datetime.fromtimestamp(core['req_info']['request_start'])

        # Parse the request variables into a dictionary.
        core["vars"] = {
            var.split("=")[0]: var.split("=", 1)[1] if "=" in var else ""
            for var in core["vars"]
        }

        # Form a request URL.
        try:
            url = core["vars"]["REQUEST_SCHEME"] + "://" + core["vars"]["HTTP_HOST"] + core["vars"]["REQUEST_URI"]
            if core["vars"]["QUERY_STRING"]: url += "?" + core["vars"]["QUERY_STRING"]
        except KeyError:
            url = None

        cores.append({
            "worker": clone_dict_without_key(worker, "cores"),
            "core": clone_dict_without_key(core, "vars", "req_info"),
            "request_vars": core["vars"],
            "request_info": core["req_info"],
            "request_url": url,
        })


# Sort requests from longest (earlier start time) to shortest.
cores.sort(key = lambda core : core["request_info"].get("request_start", datetime.datetime.min))

# Show requests.
now = datetime.datetime.now()
for core in cores:
    request_time = core["request_info"].get("request_start")
    if not request_time: continue
    url = core["request_url"]
    print(str(round((now - request_time).total_seconds(), 1)) + "s", url)
