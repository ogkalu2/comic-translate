from .dayu_widgets.message import MMessage
from PySide6.QtCore import QCoreApplication, Qt
from PySide6 import QtWidgets

class Messages:

    @staticmethod
    def show_translation_complete(parent):

        MMessage.success(
            text=QCoreApplication.translate(
                "Messages", 
                "Comic has been Translated!"
            ),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def select_font_error(parent):
        MMessage.error(
            text=QCoreApplication.translate(
                "Messages", 
                "No Font selected.\nGo to Settings > Text Rendering > Font to select or import one "
            ),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_not_logged_in_error(parent):
        MMessage.error(
            text=QCoreApplication.translate(
                "Messages",
                "Please sign in or sign up via Settings > Account to continue."
            ),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_translator_language_not_supported(parent):
        MMessage.error(
            text=QCoreApplication.translate(
                "Messages",
                "The translator does not support the selected target language. Please choose a different language or tool."
            ),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_missing_tool_error(parent, tool_name):
        MMessage.error(
            text=QCoreApplication.translate(
                "Messages",
                "No {} selected. Please select a {} in Settings > Tools."
            ).format(tool_name, tool_name),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_insufficient_credits_error(parent, details: str = None):
        """
        Show an error message when the user has insufficient credits.
        
        Args:
            parent: parent widget
            details: optional detailed message from backend
        """
        msg = QtWidgets.QMessageBox(parent)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle(QCoreApplication.translate("Messages", "Insufficient Credits"))
        msg.setText(QCoreApplication.translate(
            "Messages", 
            "Insufficient credits to perform this action.\nGo to Settings > Account to buy more credits."
        ))
        
        if details:
            msg.setDetailedText(details)
            
        ok_btn = msg.addButton(QCoreApplication.translate("Messages", "OK"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        msg.setDefaultButton(ok_btn)
        msg.exec()

    @staticmethod
    def show_custom_not_configured_error(parent):
        """
        Show an error message when Custom is selected without proper configuration.
        Guides users to use the Credits system instead.
        """
        MMessage.error(
            text=QCoreApplication.translate(
                "Messages",
                "Custom requires advanced API configuration. Most users should use the Credits system instead.\n"
                "Please sign in via Settings > Account to use credits, or configure Custom API settings in Settings > Advanced."
            ),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_error_with_copy(parent, title: str, text: str, detailed_text: str | None = None):
        """
        Show a critical error dialog where the main text is selectable and the
        full details (traceback) are placed in the Details pane. A Copy button
        is provided to copy the full details to the clipboard.

        Args:
            parent: parent widget
            title: dialog window title
            text: short error text shown in the main area
            detailed_text: optional long text (traceback) shown in Details
        """
        msg = QtWidgets.QMessageBox(parent)
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setWindowTitle(title)
        msg.setText(text)
        if detailed_text:
            msg.setDetailedText(detailed_text)

        # Allow selecting the main text
        try:
            msg.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        except Exception:
            pass

        copy_btn = msg.addButton(QCoreApplication.translate("Messages", "Copy"), QtWidgets.QMessageBox.ButtonRole.ActionRole)
        ok_btn = msg.addButton(QCoreApplication.translate("Messages", "OK"), QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(QCoreApplication.translate("Messages", "Close"), QtWidgets.QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(ok_btn)
        msg.exec()

        if msg.clickedButton() == copy_btn:
            try:
                QtWidgets.QApplication.clipboard().setText(detailed_text or text)
            except Exception:
                pass

    @staticmethod
    def show_server_error(parent, status_code: int = 500, context: str = None):
        """
        Show a user-friendly error for 5xx server issues.
        
        Args:
            parent: parent widget
            status_code: HTTP status code
            context: optional context ('translation', 'ocr', or None for generic)
        """
        messages = {
            500: QCoreApplication.translate("Messages", "An unexpected error occurred on the server.\nPlease try again later."),
            502: QCoreApplication.translate("Messages", "The server received an invalid response from an upstream provider.\nPlease try again later."),
            503: QCoreApplication.translate("Messages", "The server is currently unavailable or overloaded.\nPlease try again later."),
            504: QCoreApplication.translate("Messages", "The server timed out waiting for a response.\nPlease try again later."),
        }
        
        # Context-aware 501 message
        if status_code == 501:
            if context == 'ocr':
                text = QCoreApplication.translate("Messages", "The selected text recognition tool is currently unavailable.\nPlease select a different tool in Settings.")
            elif context == 'translation':
                text = QCoreApplication.translate("Messages", "The selected translator is currently unavailable.\nPlease select a different tool in Settings.")
            else:
                text = QCoreApplication.translate("Messages", "The selected tool is currently unavailable.\nPlease select a different tool in Settings.")
        else:
            text = messages.get(status_code, messages[500])
        
        MMessage.error(
            text=text,
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_network_error(parent):
        """
        Show a user-friendly error for network/connectivity issues.
        """
        MMessage.error(
            text=QCoreApplication.translate(
                "Messages", 
                "Unable to connect to the server.\nPlease check your internet connection."
            ),
            parent=parent,
            duration=None,
            closable=True
        )

    @staticmethod
    def show_content_flagged_error(parent, details: str = None, context: str = "Operation"):
        """
        Show a friendly error when content is blocked by safety filters.
        """
        # Determine specific messaging based on context
        if context == "OCR":
            action_msg = "Text Recognition blocked"
            suggestion = "Please try using a different Text Recognition tool."
        elif context in ("Translator", "Translation"):
            action_msg = "Translation blocked"
            suggestion = "Please try using a different translator."

        base_msg = QCoreApplication.translate(
            "Messages", 
            "{0}: The content was flagged by the AI provider's safety filters.\n{1}"
        ).format(action_msg, suggestion)
        msg_text = f"{base_msg}\n{details}" if details else base_msg

        MMessage.error(
            text=msg_text,
            parent=parent,
            duration=None,
            closable=True
        )

