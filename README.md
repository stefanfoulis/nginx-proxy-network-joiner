## How to use this proxy with other locally running projects

Optain a certificate and copy it into the certs directory following the same 
naming convention as for the sherpany.me cert.

You can get a letsencrypt wildcard cert like this (need to install certbot, 
e.g with ``brew install certbot``):

```
certbot certonly --agree-tos --config-dir letsencrypt/config --work-dir letsencrypt/work --logs-dir letsencrypt/logs --server https://acme-v02.api.letsencrypt.org/directory --manual --preferred-challenges=dns -d '*.example.com,example.com'
```

Follow the instructions and when done copy over these files:

```
cp /etc/letsencrypt/config/live/example.com/fullchain.pem ./stack/proxy/certs/example.com.crt
cp /etc/letsencrypt/config/live/example.com/privkey.pem ./stack/proxy/certs/example.com.key
```

Setup a wildcard dns entry for your domain pointing to ``127.0.0.1``.

Start the other docker-compose based project and note the network name. The
default will be ``<my_project_prefix>_default``. Use ``docker network ls`` to 
list all networks. Then:

```
docker network connect <my_project_prefix>_default obrv2_proxy_1
```

Make sure ``obrv2_proxy_1`` matches the container name of your proxy. It will 
be different if you are using a different base directory than ``obrv2``.

Now the proxy should serve the traffic of containers in the other project too, 
if they define a ``VIRTUAL_HOST`` environment variable.

If you re-create the proxy container you'll also have to re-connect the 
networks.
