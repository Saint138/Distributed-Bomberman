taskkill //F //IM py.exe 2>/dev/null
taskkill //F //IM python.exe 2>/dev/null
sleep 1
start py src/server/mainServer.py
sleep 2
start py src/server/fault_tolerance/proxy_server.py
sleep 1
start py src/client/mainClient.py
start py src/client/mainClient.py
