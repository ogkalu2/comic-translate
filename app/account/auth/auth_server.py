import http.server
import socketserver
import threading
import random
import errno
import time
import json 
import logging 
from typing import Optional
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

class AuthServerThread(QThread):
    # Emit tokens AND user_info on successful callback verification
    tokens_received = Signal(str, str, dict) # access_token, refresh_token, user_info
    error = Signal(str) # General errors

    def __init__(self, port: Optional[int] = None, expected_request_id: Optional[str] = None):
        super().__init__()
        self._port_preference = port # Store initial port choice if provided
        self.port: Optional[int] = None # Port will be determined during run()
        self.server: Optional[socketserver.TCPServer] = None
        self.max_retries = 5
        self.expected_request_id = expected_request_id # Store the ID to verify callback

    def stop_server(self):
        """Requests the server to shut down."""
        if self.server:
            logger.info(f"External request received to stop server on port {self.port}.")
            # shutdown() is thread-safe and will interrupt serve_forever()
            self.server.shutdown()
        else:
            logger.warning("Stop server requested, but server instance is not available.")

    def run(self):
        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            # Pass the parent thread instance and expected request ID
            parent_thread: AuthServerThread = self

            def do_POST(self):
                """Handle POST request from the backend containing tokens."""
                parent = self.__class__.parent_thread
                expected_id = parent.expected_request_id
                content_length = int(self.headers.get('Content-Length', 0))
                post_body = self.rfile.read(content_length)
                response_code = 500 # Default to internal error
                response_body = b"Internal Server Error"
                should_shutdown = True # Shutdown after handling (success or failure)

                logger.info(f"Received POST request on callback server (Path: {self.path})")

                if '/callback' in self.path:
                    try:
                        data = json.loads(post_body)
                        received_request_id = data.get("request_id")
                        access_token = data.get("access_token")
                        refresh_token = data.get("refresh_token") # May be None/missing
                        # Extract user_info 
                        user_info = data.get("user_info", {}) # Optional, defaults to empty dict

                        logger.debug(f"Callback Data Received: request_id={received_request_id}, user={user_info.get('email')}")

                        # 1. Verify request_id
                        if not expected_id:
                            logger.error("Server started without an expected_request_id. Cannot verify callback.")
                            response_code = 500
                            response_body = b"Server configuration error: Missing expected request ID."
                            parent.error.emit("Internal error: Server missing expected request ID.")
                        elif received_request_id != expected_id:
                            logger.warning(f"Mismatched request_id! Expected '{expected_id}', received '{received_request_id}'. Rejecting.")
                            response_code = 400 # Bad Request - invalid ID
                            response_body = b"Invalid request: request_id mismatch."
                            parent.error.emit("Authentication failed: Invalid callback received (ID mismatch).")
                        elif not access_token:
                            logger.error("Callback received without an access_token. Rejecting.")
                            response_code = 400 # Bad Request - missing essential data
                            response_body = b"Invalid request: Missing access_token."
                            parent.error.emit("Authentication failed: Invalid callback received (missing token).")
                        else:
                            # Success!
                            logger.info("Request ID verified successfully. Emitting tokens and user info.")
                            response_code = 200
                            response_body = b"Tokens received successfully by desktop app."
                            # Emit tokens and user_info before responding/shutting down
                            parent.tokens_received.emit(access_token, refresh_token or "", user_info)

                        # Send response back to backend
                        self.send_response(response_code)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(response_body)
                        logger.debug(f"Sent {response_code} response back to backend.")

                    except json.JSONDecodeError:
                        logger.error("Failed to decode JSON from callback POST body.")
                        response_code = 400
                        response_body = b"Invalid request: Malformed JSON."
                        self.send_response(response_code)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(response_body)
                        parent.error.emit("Authentication failed: Invalid data format received from backend.")
                    except Exception as e:
                        logger.error(f"Error processing callback POST: {str(e)}", exc_info=True)
                        # Try sending 500 if headers not already sent
                        if not self.wfile.closed:
                            try:
                                self.send_response(500)
                                self.send_header('Content-type', 'text/plain')
                                self.end_headers()
                                self.wfile.write(f"Internal Server Error: {str(e)}".encode())
                            except Exception as send_err:
                                logger.error(f"Error sending 500 response during exception handling: {send_err}")

                        parent.error.emit(f"Internal error processing authentication callback: {str(e)}")
                    finally:
                         # Always shutdown after handling a POST request in this flow
                        if should_shutdown and parent.server:
                            logger.debug("Requesting server shutdown from handler.")
                            # Avoid deadlock when using non-threaded servers: shutdown from another thread.
                            threading.Thread(target=parent.server.shutdown, daemon=True).start()
                else:
                    logger.warning(f"Received POST on unexpected path: {self.path}")
                    self.send_response(404)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b"Not found")
                    # Decide if unexpected POST should shut down server? Probably not.
                    should_shutdown = False

            def do_GET(self):
                """Handle GET requests - serve the JS bridge page for /callback."""
                logger.debug(f"Received GET request for {self.path}")
                
                if self.path == '/favicon.ico':
                    self.send_response(204) # No content
                    self.end_headers()
                    return

                # For /callback (or standard root), serve the bridge page
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                # HTML with JS to extract hash and POST to server
                # We use a simple inline HTML/JS payload to avoid needing external files
                html = """
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Completing Login...</title>
                        <style>
                            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f1f5f9; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                            .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); max-width: 400px; width: 100%; text-align: center; }
                            .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3b82f6; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 1rem; }
                            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                            .success { color: #10b981; font-weight: 500; }
                            .error { color: #ef4444; }
                        </style>
                    </head>
                    <body>
                        <div class="card">
                            <div id="spinner" class="spinner"></div>
                            <h3 id="title">Finishing Sign In...</h3>
                            <p id="message" style="color: #64748b;">Please wait while we complete the authentication process.</p>
                        </div>
                        <script>
                            (function() {
                                // Detect user's language (only fr, ko, zh are prefixed routes)
                                function detectLanguage() {
                                    const langs = navigator.languages || [navigator.language || navigator.userLanguage];
                                    
                                    // Return the FIRST language that matches our supported locales
                                    // This respects the user's priority order
                                    for (let i = 0; i < langs.length; i++) {
                                        const lang = langs[i];
                                        if (!lang) continue;
                                        
                                        // Check in order - if English is first, we return null immediately
                                        if (lang.startsWith('en')) return null; // English = no prefix
                                        if (lang.startsWith('fr')) return 'fr';
                                        if (lang.startsWith('ko')) return 'ko';
                                        if (lang.startsWith('zh')) return 'zh';
                                    }
                                    return null; // Default to English (no prefix)
                                }
                                
                                // 1. Extract parameters from URL fragment (hash)
                                const hash = window.location.hash.substring(1);
                                if (!hash) {
                                    document.getElementById('spinner').style.display = 'none';
                                    if (window.location.pathname.includes('callback')) {
                                        document.getElementById('title').innerText = 'Authentication Error';
                                        document.getElementById('message').innerText = 'No authentication token received in URL fragment.';
                                        document.getElementById('message').className = 'error';
                                    } else {
                                        document.getElementById('title').innerText = 'Auth Listener Active';
                                        document.getElementById('message').innerText = 'This window handles desktop authentication.';
                                    }
                                    return;
                                }

                                const params = new URLSearchParams(hash);
                                const payload = {};
                                for (const [key, value] of params.entries()) {
                                    payload[key] = value;
                                }

                                // 2. Parse user_info JSON string if present
                                if (payload.user_info) {
                                    try {
                                        payload.user_info = JSON.parse(payload.user_info);
                                    } catch (e) {
                                        console.warn("Failed to parse user_info JSON:", e);
                                    }
                                }

                                // 3. Send data to the local server via POST
                                fetch('/callback', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(payload)
                                })
                                .then(async response => {
                                    const text = await response.text();
                                    document.getElementById('spinner').style.display = 'none';
                                    
                                    if (response.ok) {
                                        // Success! Redirect to localized success page (only fr, ko, zh have prefixes)
                                        const userLang = detectLanguage();
                                        const redirectPath = userLang 
                                            ? `/${userLang}/auth/desktop-login-success` 
                                            : '/auth/desktop-login-success';
                                        
                                        window.location.href = `https://comic-translate.com${redirectPath}`;
                                    } else {
                                        document.getElementById('title').innerText = 'Sign In Failed';
                                        document.getElementById('message').innerText = text || 'The application rejected the login attempt.';
                                        document.getElementById('message').className = 'error';
                                    }
                                })
                                .catch(err => {
                                    document.getElementById('spinner').style.display = 'none';
                                    document.getElementById('title').innerText = 'Connection Error';
                                    document.getElementById('message').innerText = 'Failed to communicate with the desktop application.';
                                    document.getElementById('message').className = 'error';
                                });
                            })();
                        </script>
                    </body>
                    </html>
                    """
                self.wfile.write(html.encode("utf-8"))

            def log_message(self, format, *args):
                # Suppress default logging or customize
                # logger.debug(format % args) # Uncomment for verbose request logging
                return

        # Server Start Logic with Retry
        server_started = False
        port_to_try = self._port_preference if self._port_preference else random.randint(8001, 9000)

        for attempt in range(self.max_retries + 1): # +1 to include initial try
            try:
                # Pass the parent thread instance to the handler
                CallbackHandler.parent_thread = self

                socketserver.TCPServer.allow_reuse_address = True
                # Use threaded server so request handlers don't run inside serve_forever()
                # (prevents shutdown deadlocks and improves robustness).
                self.server = socketserver.ThreadingTCPServer(("localhost", port_to_try), CallbackHandler)
                self.server.daemon_threads = True
                self.port = port_to_try # Store the successfully bound port
                server_started = True
                logger.info(f"Auth server successfully bound to port {self.port} (Attempt {attempt + 1})")
                break # Exit loop if successful
            except OSError as e:
                if e.errno == errno.WSAEADDRINUSE or e.errno == errno.EADDRINUSE:
                    logger.warning(f"Port {port_to_try} already in use.")
                    if attempt < self.max_retries:
                        # If a specific port was requested, *don't* change it, just retry
                        if self._port_preference is not None:
                            logger.warning(f"Retrying on preferred port {self._port_preference}...")
                            port_to_try = self._port_preference # Ensure it stays the same
                        else:
                            old_port = port_to_try
                            port_to_try = random.randint(8001, 9000)
                            logger.warning(f"Retrying on new random port {port_to_try} (was {old_port})...")
                        time.sleep(0.1 * (attempt + 1)) # Slightly increasing backoff
                    else:
                        # Exhausted retries
                        err_msg = f"Server error: Failed to bind to a port after {self.max_retries + 1} attempts. Last port tried: {port_to_try}."
                        logger.error(err_msg)
                        self.error.emit(err_msg)
                        return # Exit run method
                else:
                    # Different OS error
                    err_msg = f"Server OS error during setup: {str(e)} (Port: {port_to_try})"
                    logger.error(err_msg, exc_info=True)
                    self.error.emit(err_msg)
                    return # Exit run method
            except Exception as e:
                # Catch any other unexpected error during server setup
                err_msg = f"Unexpected server setup error: {str(e)} (Port: {port_to_try})"
                logger.error(err_msg, exc_info=True)
                self.error.emit(err_msg)
                return # Exit run method

        if server_started and self.server:
            try:
                logger.info(f"Auth server running on http://localhost:{self.port}. Waiting for callback...")
                self.server.serve_forever() # Blocks until shutdown() is called
                # serve_forever exits when shutdown() is called
                logger.info(f"Server on port {self.port} serve_forever() loop exited.")
            except Exception as e:
                # This might catch errors if shutdown fails uncleanly
                logger.error(f"Error during server runtime (serve_forever): {str(e)}", exc_info=True)
                if not self.signalsBlocked(): self.error.emit(f"Error during server runtime: {str(e)}")
            finally:
                logger.debug(f"Closing server socket on port {self.port}...")
                self.server.server_close()
                logger.info(f"Server on port {self.port} closed.")
                self.server = None
        else:
            # This case should ideally be handled by the retry loop exit, but as a safeguard:
            logger.error("Server startup failed silently (server instance is None or not started).")
            if not self.signalsBlocked(): self.error.emit("Server could not be started.")

