"""Read local account configuration without embedding secrets in the app."""
import os


def groq_api_key():
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if key:
        return key
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as environment:
                value, _ = winreg.QueryValueEx(environment, 'GROQ_API_KEY')
                return value.strip() if isinstance(value, str) else ''
        except OSError:
            pass
    return ''
