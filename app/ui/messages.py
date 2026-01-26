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
    def show_signup_or_credentials_error(parent):
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
        MMessage.error(
            text=QCoreApplication.translate(
            "Messages", 
            "Insufficient credits to perform this action.\nGo to Settings > Account to buy more credits."
            ),
            parent=parent,
            duration=None,
            closable=True
        )

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
