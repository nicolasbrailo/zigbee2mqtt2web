""" Forward requests from a Flask http server to arbitrary downstream http services """
import aiohttp
import os
import signal
import ssl
import time

from flask import abort, request, Response
from zzmw_lib.logs import build_logger

log = build_logger("ServiceMagicProxy")

class ServiceMagicProxy:
    """ Proxy forwarder: will forward request from a local flask server to another http server based on
    service prefix """

    def __init__(self, service_map, www):
        self._service_map = service_map
        self._register_routes(www)

    def get_proxied_services(self):
        """Return the map of service names to their proxy URLs."""
        return self._service_map

    def on_service_announced_meta(self, svc_name, www_url):
        """Handle service announcement and restart if the www URL changed."""
        if www_url is None:
            # Service has no www, nothing to proxy so we can ignore
            return
        if svc_name not in self._service_map:
            # We don't care about this service, but let the user know that a new service is up, and we won't proxy it.
            # We could restart here to start proxying, but we'd get a lot of unnecessary restarts if a service is
            # discovered, becomes unstable, and its url changes (eg due to new port assignment)
            log.warning("New service '%s' discovered, but proxy already started. Ignoring service.", svc_name)
            return
        if self._service_map[svc_name] != www_url:
            log.error("Service '%s' changed its www path from '%s' to '%s', proxying will break. ",
                      svc_name, self._service_map[svc_name], www_url)
            log.info("This service will restart in a few seconds to trigger service-rediscovery...")
            time.sleep(3)
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)
            log.critical("Sent SIGTERM, if you're seeing this something is broken...")

    def _register_routes(self, www):
        for svc_prefix, svc_route in self._service_map.items():
            log.info("Discovered route to service %s", svc_prefix)

            # Register catch-all route for this service
            route = f'/{svc_prefix}/<path:subpath>'

            # Create wrapper that properly handles async
            # We need a closure to capture the svc_prefix value
            def make_handler(prefix):
                # Use www.serve_url style registration which handles async
                async def handler(subpath):
                    return await self._forward_to_service(prefix, subpath)
                # Set the function name for Flask
                handler.__name__ = f'proxy_{prefix}'
                return handler

            handler_func = make_handler(svc_prefix)

            # Register using Flask's route decorator syntax which handles async properly
            www.route(
                route,
                methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'],
                endpoint=f'proxy_{svc_prefix}'
            )(handler_func)
            log.info("Registered proxy route: %s -> %s", route, svc_route)

    async def _forward_to_service(self, svc_prefix, subpath):
        """Generic proxy handler that forwards requests to upstream services."""
        if svc_prefix not in self._service_map:
            log.error("Unknown service prefix: %s", svc_prefix)
            return abort(404, f"Service '{svc_prefix}' not found")

        upstream_url = self._service_map[svc_prefix]
        target_url = f"{upstream_url}/{subpath}"

        # Preserve query string
        if request.query_string:
            target_url += f"?{request.query_string.decode('utf-8')}"

        log.debug("Proxying %s %s -> %s", request.method, request.path, target_url)

        try:
            # Create SSL context that accepts self-signed certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # Prepare request kwargs
                kwargs = {
                    'timeout': aiohttp.ClientTimeout(total=5),
                    'allow_redirects': False,
                }

                # Forward request headers (excluding hop-by-hop headers)
                headers = {}
                hop_by_hop = {'connection', 'keep-alive', 'proxy-authenticate',
                             'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade'}
                for key, value in request.headers:
                    if key.lower() not in hop_by_hop:
                        headers[key] = value
                kwargs['headers'] = headers

                # Forward request body for methods that support it
                if request.method in ['POST', 'PUT', 'PATCH']:
                    data = request.get_data()
                    if data:
                        kwargs['data'] = data

                # Make the request
                async with session.request(request.method, target_url, **kwargs) as resp:
                    # Read response body
                    body = await resp.read()

                    # Forward response headers (excluding hop-by-hop headers)
                    response_headers = {}
                    for key, value in resp.headers.items():
                        if key.lower() not in hop_by_hop:
                            response_headers[key] = value

                    # Create Flask response with upstream status code and headers
                    return Response(
                        body,
                        status=resp.status,
                        headers=response_headers
                    )

        except aiohttp.ClientError as e:
            log.error("Error proxying to %s: %s", target_url, str(e))
            return abort(502, f"Error connecting to upstream service: {str(e)}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.error("Unexpected error proxying to %s: %s", target_url, str(e), exc_info=True)
            return abort(500, f"Internal proxy error: {str(e)}")
