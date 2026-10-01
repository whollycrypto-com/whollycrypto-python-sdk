"""Server-side template: creates an account. Review before running on a real installation."""
import os
from whollycrypto import OperatorClient

# Persist this key AND the exact body before the first call; reuse them on retries.
with OperatorClient(os.environ['WHOLLY_API_URL'], os.environ['WHOLLY_OPERATOR_TOKEN']) as operator:
    merchant = operator.create_merchant({
        'name': 'Example shop', 'email': os.environ['WHOLLY_NEW_ADMIN_EMAIL'],
        'external_id': 'your-customer-1042', 'onboarding': 'direct',
        'password': os.environ['WHOLLY_NEW_ADMIN_PASSWORD'], 'require_password_change': True,
        'currency': 'EUR', 'default_timezone': 'Europe/Berlin', 'starting_credit': '0',
    }, os.environ['WHOLLY_PROVISION_REQUEST_KEY'])
    print(merchant['merchant_id'])  # Never log private tokens or invitation URLs.
# Invitation alternative: onboarding='invitation', omit password; optionally set
# send_invitation_email=True with configured SMTP. Save access_link privately once.
# Replays omit secrets. Inspect the account before creating a new request key.

# Recipient's server-side acceptance, only after explicit custody acknowledgement:
# from whollycrypto import OperatorOnboardingClient
# with OperatorOnboardingClient(os.environ['WHOLLY_API_URL']) as onboarding:
#     onboarding.accept_invitation(private_token, chosen_password, custody_acknowledged)
# Normal console login still requires Basic Auth and any configured TOTP.
