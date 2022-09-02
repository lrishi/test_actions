#!/usr/bin/env python3

import _thread as thread
import sys
import json
import os
import signal
import subprocess

logging = True
logFile = None
asyncLoop = None
gsutilBucket = "gs://lrishi-test-bucket"

def log(msg):
    if not logging:
        return
    logFile.write(f"{msg}\n")
    logFile.flush()

def error_exit(code, message):
    code = int(code)
    code = code if code > 0 else  -1
    x = json.dumps({ "error": { "code": code, "message": f"{message}" } })
    print(x)
    log(x)
    exit(code)

def print_status(oid, size):
    x = {"event": "progress", "oid": f"{oid}", "bytesSoFar": int(size), "bytesSinceLast": int(size)}
    print(json.dumps(x))
    log(x)

def print_completion(oid, size, path=None, error=None):
    if not error:
        print_status(oid, size)
    x = {"event": "complete", "oid": f"{oid}" }
    if error:
        x["error"] = { "code": int(error["code"]), "message": f"{error['message']}"}
    elif path:
        x["path"] = path
    print(json.dumps(x))
    log(x)
    if error:
        return
    sys.stdout.flush()

def handle_init(st):
    print("{}")
    sys.stdout.flush()

def handle_upload(st):
    cmd = ["gsutil", "-m", "cp", f"{st['path']}", f"{gsutilBucket}/{st['oid']}"]
    proc = subprocess.Popen(cmd)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        print_completion(st['oid'], 0, error={"code": proc.returncode, "message": f"Failed to upload: {st['path']}\n, cmd: {' '.join(cmd)}, stdout: {stdout}, stderr: {stderr}"})
        return
    print_completion(st['oid'], st["size"])

def handle_download(st):
    localPath = f"./.git/lfs/tmp-data/{st['oid']}"
    cmd = ["gsutil", "cp", "-r", f"{gsutilBucket}/{st['oid']}", localPath]
    proc = subprocess.Popen(cmd)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        print_completion(st['oid'], 0, error={"code": proc.returncode, "message": f"Failed to download: {st['oid']}\n, cmd: {' '.join(cmd)}, stdout: {stdout}, stderr: {stderr}"})
        return
    print_completion(st['oid'], st["size"], path=localPath)
    

def main():
    tasks = []
    while True:
        command = sys.stdin.readline()
        try:
            st = json.loads(command)
            log(f"Received event: {st}")
            if st["event"] == "init":
                handle_init(st)
            elif st["event"] == "upload":
                thread.start_new_thread(handle_upload, (st,))
            elif st["event"] == "download":
                thread.start_new_thread(handle_download, (st,))
            elif st["event"] == "terminate":
                return
            else:
                raise Exception(f"Unknown event: {st['event']}")
        except Exception as e:
            error_exit(2, f"Protocol error: {command}, err={e}")

if __name__ == "__main__":
    try:
        if logging:
            logFile = open("/tmp/testfile", "w")
        main()
        if logFile:
            logFile.close()
    except Exception as e:
        error_exit(1, f"Failed to run, err={e}")
