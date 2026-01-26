import secrets
import logging
import urllib.parse
import requests 
import threading
import time

from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread, QSettings 
from PySide6.QtWidgets import QMessageBox
from .auth_server import AuthServerThread
from .token_storage import set_token, get_token, delete_token

logger = logging.getLogger(__name__)

# Define constants for QSettings keys
USER_INFO_GROUP = "user_info"
EMAIL_KEY = "email"
TIER_KEY = "tier"
CREDITS_KEY = "credits"
MONTHLY_CREDITS_KEY = "monthly_credits"

class SessionCheckThread(QThread):
    """Thread to validate the session in the background."""
    result = Signal(bool)

    def __init__(self, auth_client):
        super().__init__()
        self.auth_client = auth_client

    def run(self):
        is_valid = self.auth_client.validate_token()
        # If the token is valid (or we're offline and keeping the session),
        # opportunistically refresh user info. Failures are handled inside.
        if is_valid:
            self.auth_client.fetch_user_info()
        self.result.emit(is_valid)

class AuthClient(QObject): 
    auth_success = Signal(dict) 
    auth_error = Signal(str) 
    auth_cancelled = Signal()
    request_login_view = Signal(str) # Emits the URL to load
    logout_success = Signal()
    session_check_finished = Signal(bool)

    def __init__(self, api_url: str, frontend_url: str):
        super().__init__()
        self.api_url = api_url
        self.frontend_url = frontend_url
        self.current_request_id: Optional[str] = None # Store the ID for the current auth attempt
        self.auth_server_thread: Optional[AuthServerThread] = None
        self.settings = QSettings("ComicLabs", "ComicTranslate")
        self._request_lock = threading.Lock()
        self._session = requests.Session()
        # Separate session for background/non-critical calls so they don't contend
        # with token validation/refresh or per-operation requests.
        self._bg_request_lock = threading.Lock()
        self._bg_session = requests.Session()
        self._validated_token: Optional[str] = None
        self._validated_token_ok_until_monotonic: float = 0.0
        self._validated_token_ttl_s: float = 30.0

    def _clear_validation_cache(self) -> None:
        self._validated_token = None
        self._validated_token_ok_until_monotonic = 0.0

    def start_auth_flow(self):
        """Starts the new authentication flow."""
        # If a previous thread object is still referenced but already finished, clear it.
        if self.auth_server_thread and not self.auth_server_thread.isRunning():
            logger.debug("Found stale auth server thread reference; clearing.")
            self.auth_server_thread = None

        if self.auth_server_thread and self.auth_server_thread.isRunning():
            logger.warning("Authentication flow already in progress. Ignoring new request.")
            return

        # 1. Generate unique request ID
        self.current_request_id = secrets.token_urlsafe(32)
        logger.info(f"Generated request_id: {self.current_request_id}")

        # 2. Start local server to receive the token callback from backend
        # Pass the expected request_id to the server thread for verification
        self.auth_server_thread = AuthServerThread(expected_request_id=self.current_request_id)
        self.auth_server_thread.tokens_received.connect(self._handle_token_callback)
        self.auth_server_thread.error.connect(self._handle_server_error)
        self.auth_server_thread.finished.connect(self._on_server_finished)
        self.auth_server_thread.start()

        # Give the server a moment to start and potentially retry port binding
        # Let's wait briefly for the port to be potentially available.
        wait_count = 0
        while not self.auth_server_thread.port and wait_count < 20: # Wait up to 2 seconds
            QThread.msleep(100)
            wait_count += 1

        # Check if server started successfully (it emits error if not)
        if not self.auth_server_thread or not self.auth_server_thread.port:
            logger.error("Auth server thread failed to start or find a port.")
            if not self.signalsBlocked(): # Check if signals can be emitted
                self.auth_error.emit("Failed to start local authentication listener.")
            self.current_request_id = None 
            self._cleanup_server() 
            return

        actual_port = self.auth_server_thread.port
        logger.info(f"Auth server started on port: {actual_port}")

        # 3. Prepare backend authorization URL
        desktop_callback_uri = f"http://localhost:{actual_port}/callback" # Or 127.0.0.1
        params = {
            "request_id": self.current_request_id,
            "desktop_callback_uri": desktop_callback_uri,
            "prompt": "login"
        }
        # Include trailing slash to prevent production server redirect that strips query params
        login_url = f"{self.frontend_url}/login/" 
        auth_url = f"{login_url}?{urllib.parse.urlencode(params)}"
        logger.info(f"Requesting login view for: {auth_url}")

        # 4. Emit signal to request the web view instead of opening browser directly
        self.request_login_view.emit(auth_url)



    def _handle_token_callback(self, access_token: str, refresh_token: str, user_info: dict):
        """Handles the tokens and user info received from the backend via the local server."""
        logger.info("Tokens and user info received callback handled in main client.")
        try:
            # Securely store tokens using helper
            set_token("access_token", access_token)
            self._clear_validation_cache()
             
            # Always store refresh token if received
            if refresh_token:
                set_token("refresh_token", refresh_token)
            else:
                logger.warning("Refresh token was not received from backend callback.")
                delete_token("refresh_token")

            logger.info("Tokens stored successfully.")
            self.auth_success.emit(user_info)

        except Exception as e:
            logger.error(f"Error storing tokens: {e}", exc_info=True)
            self.auth_error.emit(f"Failed to store authentication tokens securely: {str(e)}")
        finally:
            self.current_request_id = None

    def _handle_server_error(self, error_message: str):
        """Handles errors emitted by the AuthServerThread."""
        logger.error(f"Auth server error: {error_message}")
        # Avoid emitting duplicate errors if cancelled
        if "cancelled by user" not in error_message:
            if not self.signalsBlocked(): # Check if signals can be emitted
                self.auth_error.emit(f"Authentication listener error: {error_message}")
        self.current_request_id = None
        # Let the finished signal handle the final cleanup via _on_server_finished
        
    def _on_server_finished(self):
        """Called when the AuthServerThread finishes execution."""
        logger.info("Auth server thread finished.")
        self._cleanup_server()

    def _cleanup_server(self):
        """Safely attempts to clear server thread reference."""
        logger.debug("Cleaning up auth server thread reference...")
        thread = self.auth_server_thread
        if thread and thread.isRunning():
            logger.warning("Cleanup called but server thread is still marked as running (might be finishing).")
        self.auth_server_thread = None
        logger.debug("Auth server thread reference cleared.")

    def shutdown(self):
        """Clean up threads before application exit."""
        logger.info("Shutting down AuthClient...")
        
        # 1. Stop AuthServerThread
        if self.auth_server_thread:
            logger.debug("Stopping AuthServerThread...")
            if self.auth_server_thread.isRunning():
                self.auth_server_thread.stop_server()
                self.auth_server_thread.quit()
                self.auth_server_thread.wait()
            self.auth_server_thread = None

        # 2. Stop SessionCheckThread
        if hasattr(self, '_session_check_thread') and self._session_check_thread:
             logger.debug("Stopping SessionCheckThread...")
             if self._session_check_thread.isRunning():
                 self._session_check_thread.quit()
                 self._session_check_thread.wait()
             self._session_check_thread = None
        
        logger.info("AuthClient shutdown complete.")

    def cancel_auth_flow(self):
        """Cancels the currently active authentication flow."""
        logger.info("Attempting to cancel authentication flow.")
        was_running = False
        if self.auth_server_thread and self.auth_server_thread.isRunning():
            logger.debug("Requesting auth server thread to stop.")
            self.auth_server_thread.stop_server() # Request shutdown
            was_running = True
            # The thread will emit finished signal upon stopping,
            # which triggers _on_server_finished for cleanup.
            # We don't wait here to avoid blocking the UI thread.
        else:
            logger.debug("No active auth server thread found or it wasn't running.")

        # Clear the request ID regardless, prevents callback mismatch if server already sent it
        self.current_request_id = None
        logger.debug("Cleared current_request_id.")

        # Emit an error signal to notify the UI only if a flow was likely active
        # This prevents emitting error if called unnecessarily
        # Check if signals are not blocked before emitting
        if was_running and not self.signalsBlocked():
            logger.info("Emitting auth_cancelled signal.")
            self.auth_cancelled.emit() 
        elif not was_running:
            logger.debug("Skipping auth_cancelled emit as no server thread was running.")

    def refresh_token(self) -> bool:
        """Refresh the access token using the stored refresh token."""
        logger.info("Attempting to refresh token...")
        try:
            refresh_token = get_token("refresh_token")
            access_token = get_token("access_token")
            if not (refresh_token and access_token):
                logger.warning("Cannot refresh: Tokens not found.")
                return False
            
            # Build headers with the existing access token
            headers = {"Authorization": f"Bearer {access_token}"}
            token_url = f"{self.api_url}/auth/v1/token" 
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
            logger.debug(f"Posting to {token_url} for token refresh.")

            with self._request_lock:
                response = self._session.post(
                    token_url, 
                    json=payload,
                    headers=headers, 
                    timeout=20
                )

            response.raise_for_status()

            token_data = response.json()
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token") 

            if not new_access_token:
                logger.error("Token refresh response missing access_token.")
                return False

            set_token("access_token", new_access_token)
            self._clear_validation_cache()
            if new_refresh_token:
                logger.info("Refresh token rotated. Storing new refresh token.")
                set_token("refresh_token", new_refresh_token)

            logger.info("Token refreshed successfully.")
            return True
        
        except requests.exceptions.HTTPError as http_err:
            try:
                error_data = response.json()
                error_desc = error_data.get('error_description') or error_data.get('error') or str(http_err)
            except Exception:
                error_desc = str(http_err)
            QMessageBox.critical(None, "Token Refresh Error", error_desc)
            logger.error(f"HTTP error during token refresh: {error_desc}")
            if response.status_code in [400, 401]:
                logger.warning("Refresh token seems invalid. Triggering logout.")
                self.logout()
            return False
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during token refresh: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(None, "Network Error", error_msg)
            return False
        
        except Exception as e:
            error_msg = f"Unexpected error during token refresh: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(None, "Error", error_msg)
            return False
        
    def is_authenticated(self) -> bool:
        """Check if user has a locally stored access token. Does NOT validate it here."""
        # This is a quick check. Validation should happen before sensitive operations.
        logger.debug("Checking for local access token...")
        try:
            access_token = get_token("access_token")
            is_present = bool(access_token)
            logger.debug(f"Access token found: {is_present}")
            return is_present
        except Exception as e:
            logger.error(f"Error checking for access token in keyring: {e}")
            return False

    def validate_token(self) -> bool:
        """
        Check the validity of the current access token with the backend.
        Triggers a refresh if the backend response indicates the token is
        invalid (either definitively expired/bad or near expiry).

        Returns:
            bool: True if the token is currently valid (and not near expiry)
                  OR if it was successfully refreshed after being reported invalid/near-expiry.
                  False if the token was reported invalid/near-expiry AND refresh failed,
                  or if there was a network/server error, or no token exists.
        """
        logger.info("Checking access token validity with backend...")
        access_token: Optional[str] = None
        try:
            access_token = get_token("access_token")
            if not access_token:
                logger.info("No access token found locally. Cannot validate.")
                return False

            now = time.monotonic()
            if (
                self._validated_token == access_token
                and now < self._validated_token_ok_until_monotonic
            ):
                logger.debug("Token validation cache hit (skipping backend validate).")
                return True

            validate_url = f"{self.api_url}/auth/v1/validate"
            headers = {"Authorization": f"Bearer {access_token}"}

            logger.debug(f"Sending validation request to {validate_url}")
            with self._request_lock:
                response = self._session.get(validate_url, headers=headers, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            is_valid = data.get("valid")

            if is_valid is True:
                # Explicitly True means valid and not near expiry
                logger.info("Token validation successful (via backend).")
                self._validated_token = access_token
                self._validated_token_ok_until_monotonic = time.monotonic() + self._validated_token_ttl_s
                return True
            elif is_valid is False:
                # Explicitly False (could be near expiry or actually invalid)
                reason = data.get("reason", "unspecified")
                status_code = response.status_code # Log status for context
                logger.info(f"Token reported as invalid by backend (status: {status_code}, reason: {reason}). Attempting refresh...")
                return self.refresh_token() # Attempt refresh
            else:
                # Response JSON is missing the 'valid' field or has an unexpected value
                logger.error(f"Backend validation response (status: {response.status_code}) missing or has invalid 'valid' field. Assuming invalid.")
                # Don't attempt refresh if the response format is broken
                return False

        except requests.exceptions.Timeout:
            logger.warning("Token validation request timed out. Assuming offline/unreachable. Keeping session.")
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.info("Token validation returned 401. Attempting refresh...")
                return self.refresh_token()
            logger.error(f"HTTP error during token validation: {str(e)}. Assuming invalid.")
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Network error during token validation: {str(e)}. Assuming offline/unreachable. Keeping session.")
            return True
        except Exception as e: # Catch keyring errors etc.
            logger.error(f"Unexpected error during token validation check setup: {e}", exc_info=True)
            return False # Fail safe

    def logout(self):
        """Clear stored credentials, user info, and notify backend."""
        logger.info("Initiating logout.")

        # If an auth flow listener is still running (e.g., due to a previous callback server hang),
        # stop it and clear state so the user can sign in again immediately.
        try:
            if self.auth_server_thread and self.auth_server_thread.isRunning():
                logger.info("Logout: Stopping active authentication listener thread.")
                self.auth_server_thread.stop_server()
            self.current_request_id = None
            self._cleanup_server()
        except Exception as e:
            logger.warning(f"Logout: Failed to stop auth listener cleanly: {e}")

        access_token: Optional[str] = None
        try:
            # Retrieve token *before* deleting it locally
            access_token = get_token("access_token")
        except Exception as e:
            logger.warning(f"Could not retrieve access token for signout notification: {e}")

        # Clear local data FIRST
        try:
            logger.debug("Deleting local tokens from keyring...")
            delete_token("access_token")
            self._clear_validation_cache()
        except Exception as e:
            # Log error but continue - local logout is priority
            logger.warning(f"Could not delete access token from keyring (might not exist): {e}")
        try:
            delete_token("refresh_token")
        except Exception as e:
            # Log error but continue
            logger.warning(f"Could not delete refresh token from keyring (might not exist): {e}")

        # Clear user info from QSettings
        logger.debug("Clearing user info from settings...")
        self.settings.beginGroup(USER_INFO_GROUP)
        self.settings.remove("") # Remove all keys within the group
        self.settings.endGroup()
        logger.info("Local tokens and user info cleared.")

        # Notify backend
        if access_token:
            try:
                logger.debug("Notifying backend of signout...")
                signout_url = f"{self.api_url}/auth/v1/signout?scope=local"
                headers = {"Authorization": f"Bearer {access_token}"}
                with self._request_lock:
                    response = self._session.post(
                        signout_url,
                        headers=headers,
                        timeout=20
                    )
                response.raise_for_status()
                logger.info("Backend successfully processed signout notification.")

            except requests.exceptions.HTTPError as http_err:
                try:
                    error_data = response.json()
                    error_desc = error_data.get('error_description') or error_data.get('error') or str(http_err)
                except Exception:
                    error_desc = str(http_err)
                QMessageBox.critical(None, "Logout Error", error_desc)
                logger.error(f"HTTP error during token refresh: {error_desc}")

            except requests.exceptions.RequestException as e:
                error_msg = f"Network error during logout: {str(e)}"
                logger.error(error_msg)
                QMessageBox.critical(None, "Logout Error", error_msg)

            except Exception as e:
                error_msg = f"Unexpected error during logout: {str(e)}"
                logger.error(error_msg, exc_info=True)
                QMessageBox.critical(None, "Logout Error", error_msg)
        else:
            logger.debug("No access token found, skipping backend signout notification.")

        # Emit signal indicating logout is complete locally
        self.logout_success.emit()
        logger.info("Logout process complete.")

    def fetch_user_info(self):
        """Fetch the latest email/tier/credits from the backend and emit auth_success."""
        try:
            token = get_token("access_token")
            if not token:
                self.auth_error.emit("No access token available for fetching user info")
                return
            headers = {"Authorization": f"Bearer {token}"}
            with self._bg_request_lock:
                response = self._bg_session.get(f"{self.api_url}/auth/v1/user_info", headers=headers, timeout=10)
            response.raise_for_status()
            user_info = response.json()
            # Re-use the same signal that SettingsPage.handle_auth_success listens on
            self.auth_success.emit(user_info)
        except requests.exceptions.RequestException as e:
            # Treat network errors as non-fatal (e.g., user is offline). Keep cached user info.
            logger.debug(f"Could not refresh user info (offline/unreachable): {e}")
        except Exception as e:
            self.auth_error.emit(f"Failed to fetch user info: {e}")

    def check_session_async(self):
        """Validates the session in a background thread."""
        logger.debug("Starting async session check...")
        try:
            if hasattr(self, "_session_check_thread") and self._session_check_thread:
                if self._session_check_thread.isRunning():
                    logger.debug("Async session check already running; skipping duplicate start.")
                    return
        except Exception:
            pass

        if not self.is_authenticated():
            logger.debug("No access token present; skipping async session check.")
            return
        self._session_check_thread = SessionCheckThread(self)
        self._session_check_thread.result.connect(self._handle_session_check_result)
        self._session_check_thread.finished.connect(self._session_check_thread.deleteLater)
        self._session_check_thread.start()

    def _handle_session_check_result(self, is_valid: bool):
        logger.debug(f"Async session check finished. Valid: {is_valid}")
        self.session_check_finished.emit(is_valid)



