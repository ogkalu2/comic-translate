from PySide6 import QtWidgets, QtCore
from ..dayu_widgets.label import MLabel
from ..dayu_widgets.push_button import MPushButton
from app.account.config import FRONTEND_BASE_URL

class AccountPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        account_layout = QtWidgets.QVBoxLayout(self)
        account_layout.setContentsMargins(20, 20, 20, 20)

        # Use a QStackedWidget to properly handle switching between logged in/out states
        self.account_stack = QtWidgets.QStackedWidget()

        # Logged Out
        self.logged_out_widget = QtWidgets.QWidget()
        logged_out_layout = QtWidgets.QVBoxLayout(self.logged_out_widget)
        logged_out_layout.setContentsMargins(0, 0, 0, 0)
        logged_out_layout.setSpacing(15)

        title_label = MLabel(self.tr("Sign in to Comic Translate")).h3()
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        description_text = self.tr(
            "Sign in to use Comic Translate, see your credits balance, "
            "and purchase additional credits."
        )
        description_label = MLabel(description_text)
        description_label.setWordWrap(True)
        description_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.sign_in_button = MPushButton(self.tr("Sign In"))
        self.sign_in_button.setFixedWidth(150)

        logged_out_layout.addWidget(title_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        logged_out_layout.addSpacing(10)
        logged_out_layout.addWidget(description_label)
        logged_out_layout.addSpacing(20)
        logged_out_layout.addWidget(self.sign_in_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        logged_out_layout.addWidget(self.sign_in_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Link to credits costs (logged out)
        link_text = self.tr("See model credit costs")
        self.view_costs_link_out = MLabel(f'<a href="{FRONTEND_BASE_URL}/pricing/credits/" style="color: #4da6ff; text-decoration: underline; font-size: 11px;">{link_text}</a>')
        self.view_costs_link_out.setOpenExternalLinks(True)
        self.view_costs_link_out.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.view_costs_link_out.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.view_costs_link_out.setToolTip(f"{FRONTEND_BASE_URL}/pricing/credits/")
        logged_out_layout.addSpacing(10)
        logged_out_layout.addWidget(self.view_costs_link_out)
        
        logged_out_layout.addStretch(1)

        # Logged In
        self.logged_in_widget = QtWidgets.QWidget()
        logged_in_layout = QtWidgets.QVBoxLayout(self.logged_in_widget)
        logged_in_layout.setContentsMargins(0, 0, 0, 0)
        logged_in_layout.setSpacing(10)

        account_info_label = MLabel(self.tr("Account Information")).h4()

        email_layout = QtWidgets.QHBoxLayout()
        email_title_label = MLabel(self.tr("Email:")).strong()
        self.email_value_label = MLabel("...")
        email_layout.addWidget(email_title_label)
        email_layout.addWidget(self.email_value_label)
        email_layout.addStretch(1)

        tier_layout = QtWidgets.QHBoxLayout()
        tier_title_label = MLabel(self.tr("Subscription Tier:")).strong()
        self.tier_value_label = MLabel("...")
        tier_layout.addWidget(tier_title_label)
        tier_layout.addWidget(self.tier_value_label)
        tier_layout.addStretch(1)

        credits_layout = QtWidgets.QHBoxLayout()
        credits_title_label = MLabel(self.tr("Credits:")).strong()
        self.credits_value_label = MLabel("...")
        credits_layout.addWidget(credits_title_label)
        credits_layout.addWidget(self.credits_value_label)

        credits_layout.addWidget(self.credits_value_label)
        credits_layout.addStretch(1)

        # Link to credits costs (logged in) - below info block
        # Link to credits costs (logged in) - below info block
        link_text_in = self.tr("See model credit costs")
        self.view_costs_link_in = MLabel(f'<a href="{FRONTEND_BASE_URL}/pricing/credits/" style="color: #4da6ff; text-decoration: underline; font-size: 11px;">{link_text_in}</a>')
        self.view_costs_link_in.setOpenExternalLinks(True)
        self.view_costs_link_in.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.view_costs_link_in.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.view_costs_link_in.setToolTip(f"{FRONTEND_BASE_URL}/pricing/credits/")

        self.buy_credits_button = MPushButton(self.tr("Buy Credits"))
        self.buy_credits_button.setFixedWidth(150)

        self.sign_out_button = MPushButton(self.tr("Sign Out"))
        self.sign_out_button.setFixedWidth(150)

        logged_in_layout.addWidget(account_info_label)
        logged_in_layout.addSpacing(15)
        logged_in_layout.addLayout(email_layout)
        logged_in_layout.addLayout(tier_layout)
        logged_in_layout.addLayout(credits_layout)
        logged_in_layout.addSpacing(5)
        logged_in_layout.addWidget(self.view_costs_link_in)
        logged_in_layout.addStretch(1)
        logged_in_layout.addWidget(self.buy_credits_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        logged_in_layout.addWidget(self.sign_out_button, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        logged_in_layout.addSpacing(20)

        # Add both widgets to the stacked widget
        self.account_stack.addWidget(self.logged_out_widget)  # Index 0
        self.account_stack.addWidget(self.logged_in_widget)   # Index 1
        
        # Set initial state to logged out
        self.account_stack.setCurrentIndex(0)

        # Add the stack to the main layout
        account_layout.addWidget(self.account_stack)
        account_layout.addStretch()

        # Set size policy to match other pages
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Maximum)

    def show_logged_out(self):
        """Show the logged out state."""
        self.account_stack.setCurrentIndex(0)
        self.updateGeometry()

    def show_logged_in(self):
        """Show the logged in state."""
        self.account_stack.setCurrentIndex(1)
        self.updateGeometry()
