from allauth.account.forms import LoginForm
from django.forms import PasswordInput


class ClaimSenseLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Do not offer email password recovery until an email service is configured.
        self.fields['password'].widget = PasswordInput(attrs={'autocomplete': 'current-password'})
