uvicorn main:app --host 127.0.0.1 --port 8001 --reload
- this means start a uvicorn(an asgi server) server at this host and port and 
route the requestt to this application(an asgi application) 

- how the server forwards these requests is defined in the interface 

- pip : just a python package installer which installes the packages in the currently active 
    env 

- uv : installer , dependency resolver , environment mangement(??)
