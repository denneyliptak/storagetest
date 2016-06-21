# storagetest

**Prerequisites:**
Install python-dev, then pip, then psutil
```
sudo apt-get install python-dev
sudo apt-get install python-pip
sudo pip install psutil
```

**client.py -- usage**
```
python client.py --path "/home/heavyd/tmpdata" --time 10 --chunk_size_mb 50 --rollover_size_mb 100 --server localhost --port 9000
where:
  --path: location on the mountpoint to run write tests against
  --time: duration of the write test, in seconds
  --chunk_size_mb: size (MB) of chunks written to filesystem
  --rollover_size_mb: size (MB) before data file rolls over
  --server: hostname (if name resolution is available) or IP or server utility
  --port: port number for server utility (defaults to 9000)
```

**server.py -- usage**
```
python server.py ---server localhost --port 9000
where:
  --server: hostname (if name resolution is available) or IP or server utility
  --port: port number for server utility (defaults to 9000)
```
